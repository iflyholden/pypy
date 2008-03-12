"""
RPython support code for the hotpath policy.
"""

from pypy.jit.timeshifter import rtimeshift, rvalue
from pypy.rlib.objectmodel import we_are_translated
from pypy.rpython.annlowlevel import cachedtype, base_ptr_lltype
from pypy.rpython.annlowlevel import llhelper
from pypy.rpython.lltypesystem import lltype, llmemory


def setup_jitstate(interp, jitstate, greenargs, redargs,
                   bytecode, graphsigtoken):
    frame = rtimeshift.VirtualFrame(None, None)
    interp.jitstate = jitstate
    interp.frame = jitstate.frame = frame
    interp.frame.pc = 0
    interp.frame.bytecode = bytecode
    interp.frame.local_boxes = redargs
    interp.frame.local_green = greenargs
    interp.graphsigtoken = graphsigtoken

def leave_graph(interp):
    jitstate = interp.jitstate
    if jitstate is None:
        return
    exceptiondesc = interp.exceptiondesc
    builder = jitstate.curbuilder
    #for virtualizable_box in jitstate.virtualizables:
    #    assert isinstance(virtualizable_box, rvalue.PtrRedBox)
    #    content = virtualizable_box.content
    #    assert isinstance(content, rcontainer.VirtualizableStruct)
    #    content.store_back(jitstate)        
    exceptiondesc.store_global_excdata(jitstate)
    jitstate.curbuilder.finish_and_return(interp.graphsigtoken, None)
    jitstate.curbuilder = None

def compile(interp):
    jitstate = interp.jitstate
    builder = jitstate.curbuilder
    try:
        interp.bytecode_loop()
    except FinishedCompiling:
        pass
    except GenerateReturn:
        leave_graph(interp)
    else:
        leave_graph(interp)
    builder.show_incremental_progress()

def report_compile_time_exception(interp, e):
    if not we_are_translated():
        from pypy.jit.rainbow.interpreter import log
        import sys, pdb, traceback
        msg = str(e)
        if msg: msg = ': ' + msg
        msg = e.__class__.__name__ + msg
        log.ERROR("*** compilation-time error ***")
        log.ERROR(msg)
        traceback.print_exc()
        print >> sys.stderr
        pdb.post_mortem(sys.exc_info()[2])
    else:
        msg = 'Note: the JIT got a compile-time exception: %s' % (e,)
        lloperation.llop.debug_print(lltype.Void, msg)
    interp.debug_trace("ERROR:", "compile-time exception:", e)

# ____________________________________________________________

class FinishedCompiling(Exception):
    pass

class GenerateReturn(Exception):
    pass

class MeasurePoint(object):
    pass

class HotPromotionDesc:
    __metaclass__ = cachedtype

    def __init__(self, ERASED, interpreter, threshold, fallbackinterp):
        self.exceptiondesc = interpreter.exceptiondesc
        self.gv_constant_one = interpreter.rgenop.constPrebuiltGlobal(1)

        def ll_reach_fallback_point(fallback_point_ptr, value, framebase):
            try:
                fbp = fallback_point_ptr     # XXX cast
                assert lltype.typeOf(value) is lltype.Bool   # XXX for now
                if value:
                    counter = fbp.truepath_counter
                    pc = fbp.truepath_pc
                else:
                    counter = fbp.falsepath_counter
                    pc = fbp.falsepath_pc
                assert counter >= 0, (
                    "reaching a fallback point for an already-compiled path")
                counter += 1

                if counter >= threshold:
                    # this is a hot path, compile it
                    interpreter.debug_trace("jit_resume", "bool_path", value,
                        "in", fbp.saved_jitstate.frame.bytecode.name)
                    gv_value = interpreter.rgenop.genconst(value)
                    fbp.compile_hot_path(interpreter, gv_value, pc)
                    if value:
                        fbp.truepath_counter = -1    # means "compiled"
                    else:
                        fbp.falsepath_counter = -1   # means "compiled"
                    # Done.  We return without an exception set, which causes
                    # our caller (the machine code produced by hotsplit()) to
                    # loop back to the flexswitch and execute the
                    # newly-generated code.
                    interpreter.debug_trace("resume_machine_code")
                    return
                else:
                    # path is still cold
                    if value:
                        fbp.truepath_counter = counter
                    else:
                        fbp.falsepath_counter = counter

            except Exception, e:
                report_compile_time_exception(interpreter, e)

            # exceptions below at run-time exceptions, we let them propagate
            fallbackinterp.run(fbp, framebase, pc)
            # If the fallback interpreter reached the next jit_merge_point(),
            # it raised ContinueRunningNormally().  This exception is
            # caught by portal_runner() from hotpath.py in order to loop
            # back to the beginning of the portal.
            assert 0, "unreachable"

        self.ll_reach_fallback_point = ll_reach_fallback_point
        #ll_reach_fallback_point._debugexc = True

        FUNCTYPE = lltype.FuncType([base_ptr_lltype(), ERASED,
                                    llmemory.Address], lltype.Void)
        FUNCPTRTYPE = lltype.Ptr(FUNCTYPE)
        self.FUNCPTRTYPE = FUNCPTRTYPE
        self.sigtoken = interpreter.rgenop.sigToken(FUNCTYPE)

        def get_gv_reach_fallback_point(builder):
            fnptr = llhelper(FUNCPTRTYPE, ll_reach_fallback_point)
            # ^^^ the llhelper cannot be attached on 'self' directly, because
            # the translator needs to see its construction done by RPython code
            return builder.rgenop.genconst(fnptr)
        self.get_gv_reach_fallback_point = get_gv_reach_fallback_point

    def _freeze_(self):
        return True


class FallbackPoint(object):
    falsepath_counter = 0     # -1 after this path was compiled
    truepath_counter = 0      # -1 after this path was compiled

    def __init__(self, jitstate, flexswitch, frameinfo,
                 falsepath_pc, truepath_pc):
        # XXX we should probably trim down the jitstate once our caller
        # is done with it, to avoid keeping too much stuff in memory
        self.saved_jitstate = jitstate
        self.flexswitch = flexswitch
        self.frameinfo = frameinfo
        # ^^^ 'frameinfo' describes where the machine code stored all
        # its GenVars, so that we can fish these values to pass them
        # to the fallback interpreter
        self.falsepath_pc = falsepath_pc
        self.truepath_pc = truepath_pc

    def compile_hot_path(self, interpreter, gv_case, pc):
        if self.falsepath_counter == -1 or self.truepath_counter == -1:
            # the other path was already compiled, we can reuse the jitstate
            jitstate = self.saved_jitstate
            self.saved_jitstate = None
        else:
            # clone the jitstate
            memo = rvalue.copy_memo()
            jitstate = self.saved_jitstate.clone(memo)
        interpreter.newjitstate(jitstate)
        interpreter.frame.pc = pc
        jitstate.curbuilder = self.flexswitch.add_case(gv_case)
        compile(interpreter)

    # hack for testing: make the llinterpreter believe this is a Ptr to base
    # instance
    _TYPE = base_ptr_lltype()


def hotsplit(jitstate, hotpromotiondesc, switchbox, falsepath_pc, truepath_pc):
    # produce a Bool flexswitch for now
    incoming = jitstate.enter_block_sweep_virtualizables()
    switchblock = rtimeshift.enter_next_block(jitstate, incoming)
    gv_switchvar = switchbox.genvar
    incoming_gv = [box.genvar for box in incoming]
    flexswitch, default_builder = jitstate.curbuilder.flexswitch(gv_switchvar,
                                                                 incoming_gv)
    jitstate.curbuilder = default_builder
    # default case of the switch:
    frameinfo = default_builder.get_frame_info(incoming_gv)
    fbp = FallbackPoint(jitstate, flexswitch, frameinfo,
                        falsepath_pc, truepath_pc)
    ll_fbp = fbp        # XXX doesn't translate
    gv_fbp = default_builder.rgenop.genconst(ll_fbp)
    gv_switchvar = switchbox.genvar
    gv_fnptr = hotpromotiondesc.get_gv_reach_fallback_point(default_builder)
    gv_framebase = default_builder.genop_get_frame_base()
    default_builder.genop_call(hotpromotiondesc.sigtoken,
                               gv_fnptr,
                               [gv_fbp, gv_switchvar, gv_framebase])
    # The call above may either return normally, meaning that more machine
    # code was compiled and we should loop back to 'switchblock' to enter it,
    # or it may have set an exception.
    exceptiondesc = hotpromotiondesc.exceptiondesc
    gv_exc_type = exceptiondesc.genop_get_exc_type(default_builder)
    gv_noexc = default_builder.genop_ptr_iszero(
        exceptiondesc.exc_type_kind, gv_exc_type)
    excpath_builder = default_builder.jump_if_false(gv_noexc, [])
    default_builder.finish_and_goto(incoming_gv, switchblock)

    jitstate.curbuilder = excpath_builder
    excpath_builder.start_writing()
    raise GenerateReturn
