import sys
from pypy.rlib import rrandom
from pypy.rlib.rarithmetic import intmask
from pypy.lang.smalltalk import constants
from pypy.tool.pairtype import extendabletype
from pypy.rlib.objectmodel import instantiate
from pypy.lang.smalltalk.tool.bitmanipulation import splitter

class W_Object(object):
    __slots__ = ()    # no RPython-level instance variables allowed in W_Object

    def size(self):
        return 0

    def varsize(self):
        return self.size()

    def primsize(self):
        return self.size()

    def getclass(self):
        raise NotImplementedError

    def gethash(self):
        raise NotImplementedError

    def at0(self, index0):
        raise NotImplementedError

    def atput0(self, index0, w_value):
        raise NotImplementedError

    def fetch(self, n0):
        raise NotImplementedError
        
    def store(self, n0, w_value):    
        raise NotImplementedError

    def invariant(self):
        return True

    def shadow_of_my_class(self):
        return self.getclass().as_class_get_shadow()

    def shallow_equals(self,other):
        return self == other

    def equals(self, other):
        return self.shallow_equals(other)

class W_SmallInteger(W_Object):
    __slots__ = ('value',)     # the only allowed slot here

    def __init__(self, value):
        self.value = value

    def getclass(self):
        from pypy.lang.smalltalk.classtable import w_SmallInteger
        return w_SmallInteger

    def gethash(self):
        return self.value

    def invariant(self):
        return isinstance(self.value, int)

    def __repr__(self):
        return "W_SmallInteger(%d)" % self.value

    def shallow_equals(self, other):
        if not isinstance(other, W_SmallInteger):
            return False
        return self.value == other.value

class W_Float(W_Object):
    def __init__(self, value):
        self.value = value

    def getclass(self):
        from pypy.lang.smalltalk.classtable import w_Float
        return w_Float

    def gethash(self):
        return 41    # XXX check this

    def invariant(self):
        return self.value is not None        # XXX but later:
        #return isinstance(self.value, float)
    def __repr__(self):
        return "W_Float(%f)" % self.value

    def shallow_equals(self, other):
        if not isinstance(other, W_Float):
            return False
        return self.value == other.value

class W_AbstractObjectWithIdentityHash(W_Object):
    #XXX maybe this is too extreme, but it's very random
    hash_generator = rrandom.Random()
    UNASSIGNED_HASH = sys.maxint

    hash = UNASSIGNED_HASH # default value

    def gethash(self):
        if self.hash == self.UNASSIGNED_HASH:
            self.hash = hash = intmask(self.hash_generator.genrand32()) // 2
            return hash
        return self.hash

    def invariant(self):
        return isinstance(self.hash, int)

class W_AbstractObjectWithClassReference(W_AbstractObjectWithIdentityHash):
    """ The base class of objects that store 'w_class' explicitly. """

    def __init__(self, w_class):
        if w_class is not None:     # it's None only for testing
            assert isinstance(w_class, W_PointersObject)
        self.w_class = w_class

    def getclass(self):
        return self.w_class

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self)

    def __str__(self):
        if isinstance(self, W_PointersObject) and self._shadow is not None:
            return self._shadow.getname()
        else:
            return "a %s" % (self.shadow_of_my_class().name or '?',)

    def invariant(self):
        return (W_AbstractObjectWithIdentityHash.invariant(self) and
                isinstance(self.w_class, W_PointersObject))


class W_PointersObject(W_AbstractObjectWithClassReference):
    """ The normal object """
    
    _shadow = None # Default value

    def __init__(self, w_class, size):
        W_AbstractObjectWithClassReference.__init__(self, w_class)
        self._vars = [w_nil] * size

    def at0(self, index0):
        return self.fetch(index0)

    def atput0(self, index0, w_value):
        self.store(index0, w_value)

    def fetch(self, n0):
        return self._vars[n0]
        
    def store(self, n0, w_value):    
        if self._shadow is not None:
            self._shadow.invalidate()
        self._vars[n0] = w_value

    def fetchvarpointer(self, idx):
        return self._vars[idx+self.instsize()]

    def storevarpointer(self, idx, value):
        self._vars[idx+self.instsize()] = value

    def varsize(self):
        return self.size() - self.shadow_of_my_class().instsize()

    def instsize(self):
        return self.getclass().as_class_get_shadow().instsize()

    def primsize(self):
        return self.varsize()

    def size(self):
        return len(self._vars)

    def invariant(self):
        return (W_AbstractObjectWithClassReference.invariant(self) and
                isinstance(self._vars, list))

    # XXX XXX
    # Need to find better way of handling overloading of shadows!!!
    def setshadow(self, shadow):
        self._shadow = shadow

    def as_special_get_shadow(self, TheClass):
        shadow = self._shadow
        if shadow is None:
            shadow = TheClass(self)
        elif not isinstance(shadow, TheClass):
            shadow.invalidate()
            shadow = TheClass(self)
        shadow.check_for_updates()
        return shadow

    def as_class_get_shadow(self):
        from pypy.lang.smalltalk.shadow import ClassShadow
        shadow = self.as_special_get_shadow(ClassShadow)
        return shadow

    def as_link_get_shadow(self):
        from pypy.lang.smalltalk.shadow import LinkShadow
        return self.as_special_get_shadow(LinkShadow)
    
    def as_semaphore_get_shadow(self):
        from pypy.lang.smalltalk.shadow import SemaphoreShadow
        return self.as_special_get_shadow(SemaphoreShadow)

    def as_linkedlist_get_shadow(self):
        from pypy.lang.smalltalk.shadow import LinkedListShadow
        return self.as_special_get_shadow(LinkedListShadow)

    def as_process_get_shadow(self):
        from pypy.lang.smalltalk.shadow import ProcessShadow
        return self.as_special_get_shadow(ProcessShadow)

    def as_scheduler_get_shadow(self):
        from pypy.lang.smalltalk.shadow import SchedulerShadow
        return self.as_special_get_shadow(SchedulerShadow)

    def as_association_get_shadow(self):
        from pypy.lang.smalltalk.shadow import AssociationShadow
        return self.as_special_get_shadow(AssociationShadow)

    def as_blockcontext_get_shadow(self):
        from pypy.lang.smalltalk.shadow import BlockContextShadow
        return self.as_special_get_shadow(BlockContextShadow)

    def as_methodcontext_get_shadow(self):
        from pypy.lang.smalltalk.shadow import MethodContextShadow
        return self.as_special_get_shadow(MethodContextShadow)

    def as_context_get_shadow(self):
        from pypy.lang.smalltalk.shadow import ContextPartShadow
        return self.as_special_get_shadow(ContextPartShadow)

    def equals(self, other):
        if not isinstance(other, W_PointersObject):
            return False
        if not other.getclass() == self.getclass():
            return False
        if not other.size() == self.size():
            return False
        for i in range(self.size()):
            if not other.fetch(i).shallow_equals(self.fetch(i)):
                return False
        return True

class W_BytesObject(W_AbstractObjectWithClassReference):
    def __init__(self, w_class, size):
        W_AbstractObjectWithClassReference.__init__(self, w_class)
        self.bytes = ['\x00'] * size

    def at0(self, index0):
        from pypy.lang.smalltalk import utility
        return utility.wrap_int(ord(self.getchar(index0)))
       
    def atput0(self, index0, w_value):
        from pypy.lang.smalltalk import utility
        self.setchar(index0, chr(utility.unwrap_int(w_value)))

    def getchar(self, n0):
        return self.bytes[n0]
    
    def setchar(self, n0, character):
        assert len(character) == 1
        self.bytes[n0] = character

    def size(self):
        return len(self.bytes)    

    def __str__(self):
        return self.as_string()

    def __repr__(self):
        return "<W_BytesObject %r>" % (self.as_string(),)

    def as_string(self):
        return "".join(self.bytes)

    def invariant(self):
        if not W_AbstractObjectWithClassReference.invariant(self):
            return False
        for c in self.bytes:
            if not isinstance(c, str) or len(c) != 1:
                return False
        return True

    def shallow_equals(self, other):
        if not isinstance(other,W_BytesObject):
            return False
        return self.bytes == other.bytes

class W_WordsObject(W_AbstractObjectWithClassReference):
    def __init__(self, w_class, size):
        W_AbstractObjectWithClassReference.__init__(self, w_class)
        self.words = [0] * size
        
    def at0(self, index0):
        from pypy.lang.smalltalk import utility
        return utility.wrap_int(self.getword(index0))
       
    def atput0(self, index0, w_value):
        from pypy.lang.smalltalk import utility
        self.setword(index0, utility.unwrap_int(w_value))

    def getword(self, n):
        return self.words[n]
        
    def setword(self, n, word):
        self.words[n] = word        

    def size(self):
        return len(self.words)   

    def invariant(self):
        return (W_AbstractObjectWithClassReference.invariant(self) and
                isinstance(self.words, list))

    def shallow_equals(self, other):
        if not isinstance(other,W_WordsObject):
            return False
        return self.words == other.words

class W_CompiledMethod(W_AbstractObjectWithIdentityHash):
    """My instances are methods suitable for interpretation by the virtual machine.  This is the only class in the system whose instances intermix both indexable pointer fields and indexable integer fields.

    The current format of a CompiledMethod is as follows:

        header (4 bytes)
        literals (4 bytes each)
        bytecodes  (variable)
        trailer (variable)

    The header is a 30-bit integer with the following format:

    (index 0)   9 bits: main part of primitive number   (#primitive)
    (index 9)   8 bits: number of literals (#numLiterals)
    (index 17)  1 bit:  whether a large frame size is needed (#frameSize)
    (index 18)  6 bits: number of temporary variables (#numTemps)
    (index 24)  4 bits: number of arguments to the method (#numArgs)
    (index 28)  1 bit:  high-bit of primitive number (#primitive)
    (index 29)  1 bit:  flag bit, ignored by the VM  (#flag)

    The trailer has two variant formats.  In the first variant, the last byte is at least 252 and the last four bytes represent a source pointer into one of the sources files (see #sourcePointer).  In the second variant, the last byte is less than 252, and the last several bytes are a compressed version of the names of the method's temporary variables.  The number of bytes used for this purpose is the value of the last byte in the method.
    """

    def __init__(self, bytecount=0, header=0):
        self.setheader(header)
        self.bytes = "\x00"*bytecount

    def compiledin(self):  
        if self.w_compiledin is None:
            # (Blue book, p 607) All CompiledMethods that contain extended-super bytecodes have the clain which they are found as their last literal variable.   
            # Last of the literals is an association with compiledin
            # as a class
            w_association = self.literals[-1]
            s_association = w_association.as_association_get_shadow()
            self.w_compiledin = s_association.value()
        return self.w_compiledin

    def getclass(self):
        from pypy.lang.smalltalk.classtable import w_CompiledMethod
        return w_CompiledMethod

    def getliteral(self, index):
                                    # We changed this part
        return self.literals[index] #+ constants.LITERAL_START]

    def getliteralsymbol(self, index):
        w_literal = self.getliteral(index)
        assert isinstance(w_literal, W_BytesObject)
        return w_literal.as_string()    # XXX performance issue here

    def create_frame(self, receiver, arguments, sender = None):
        assert len(arguments) == self.argsize
        return W_MethodContext(self, receiver, arguments, sender)

    def __str__(self):
        from pypy.lang.smalltalk.interpreter import BYTECODE_TABLE
        return ("\n\nBytecode:\n---------------------\n" +
                "\n".join([BYTECODE_TABLE[ord(i)].__name__ + " " + str(ord(i)) for i in self.bytes]) +
                "\n---------------------\n")

    def invariant(self):
        return (W_Object.invariant(self) and
                hasattr(self, 'literals') and
                self.literals is not None and 
                hasattr(self, 'bytes') and
                self.bytes is not None and 
                hasattr(self, 'argsize') and
                self.argsize is not None and 
                hasattr(self, 'tempsize') and
                self.tempsize is not None and 
                hasattr(self, 'primitive') and
                self.primitive is not None)       

    def size(self):
        return self.headersize() + self.getliteralsize() + len(self.bytes) 

    def getliteralsize(self):
        return self.literalsize * constants.BYTES_PER_WORD

    def headersize(self):
        return constants.BYTES_PER_WORD

    def getheader(self):
        return self.header

    def setheader(self, header):
        #(index 0)  9 bits: main part of primitive number   (#primitive)
        #(index 9)  8 bits: number of literals (#numLiterals)
        #(index 17) 1 bit:  whether a large frame size is needed (#frameSize)
        #(index 18) 6 bits: number of temporary variables (#numTemps)
        #(index 24) 4 bits: number of arguments to the method (#numArgs)
        #(index 28) 1 bit:  high-bit of primitive number (#primitive)
        #(index 29) 1 bit:  flag bit, ignored by the VM  (#flag)
        primitive, literalsize, islarge, tempsize, numargs, highbit = (
            splitter[9,8,1,6,4,1](header))
        primitive = primitive + (highbit << 10) ##XXX todo, check this
        self.literalsize = literalsize
        self.literals = [w_nil] * self.literalsize
        self.header = header
        self.argsize = numargs
        self.tempsize = tempsize
        self.primitive = primitive
        self.w_compiledin = None

    def literalat0(self, index0):
        if index0 == 0:
            from pypy.lang.smalltalk import utility
            return utility.wrap_int(self.getheader())
        else:
            return self.literals[index0-1]

    def literalatput0(self, index0, w_value):
        if index0 == 0:
            from pypy.lang.smalltalk import utility
            header = utility.unwrap_int(w_value)
            self.setheader(header)
        else:
            self.literals[index0-1] = w_value

    def fetchbyte(self, index1):
        index0 = index1 - 1
        index0 -= self.getliteralsize()
        assert index0 < len(self.bytes)
        return self.bytes[index0]

    def store(self, index0, w_v):
        self.atput0(index0, w_v)

    def at0(self, index0):
        from pypy.lang.smalltalk import utility
        # XXX Not tested
        index0 -= self.headersize()
        if index0 < self.getliteralsize():
            self.literalat0(index0)
        else:
            index0 = index0 - self.getliteralsize()
            assert index0 < len(self.bytes)
            return utility.wrap_int(ord(self.bytes[index0]))
        
    def atput0(self, index0, w_value):
        from pypy.lang.smalltalk import utility
        # XXX Not tested
        index0 -= self.headersize()
        if index0 < self.getliteralsize():
            self.literalatput0(index0, w_value)
        else:
            # XXX use to-be-written unwrap_char
            index0 = index0 - self.getliteralsize()
            self.setchar(index0, chr(utility.unwrap_int(w_value)))

    def setchar(self, index0, character):
        assert index0 >= 0
        self.bytes = (self.bytes[:index0] + character +
                      self.bytes[index0 + 1:])

class W_ContextPart(W_AbstractObjectWithIdentityHash):

    __metaclass__ = extendabletype
    
    def __init__(self, s_home, s_sender):
        self._stack = []
        self._pc = 0
        #assert isinstance(s_home, W_MethodContext)
        self._s_home = s_home
        #assert w_sender is None or isinstance(w_sender, W_ContextPart)
        self._s_sender = s_sender

    def as_context_get_shadow(self):
        # Backward compatibility
        return self

    def w_self(self):
        # Backward compatibility
        return self

    def pc(self):
        return self._pc

    def stack(self):
        return self._stack

    def store_pc(self, pc):
        self._pc = pc

    def w_receiver(self):
        " Return self of the method, or the method that contains the block "
        return self.s_home().w_receiver()

    def s_home(self):
        return self._s_home

    def s_sender(self):
        if self._s_sender:
            return self._s_sender    

    def store_s_sender(self, s_sender):
        self._s_sender = s_sender

    def stackpointer(self):
        return len(self.stack()) + self.stackstart() - 1
    # ______________________________________________________________________
    # Imitate the primitive accessors
    
    def fetch(self, index):
        from pypy.lang.smalltalk import utility, objtable
        if index == constants.CTXPART_SENDER_INDEX:
            sender = self.s_sender()
            if sender is None:
                return objtable.w_nil
            else:
                return sender.w_self()
        elif index == constants.CTXPART_PC_INDEX:
            return utility.wrap_int(self.pc())
        elif index == constants.CTXPART_STACKP_INDEX:
            return utility.wrap_int(self.stackpointer())
        
        # Invalid!
        raise IndexError

    def store(self, index, w_value):
        # XXX Untested code...
        from pypy.lang.smalltalk import utility, objtable
        if index == constants.CTXPART_SENDER_INDEX:
            if w_value != objtable.w_nil:
                self._s_sender = w_value.as_context_get_shadow()
        elif index == constants.CTXPART_PC_INDEX:
            self._pc = utility.unwrap_int(w_value)
        elif index == constants.CTXPART_STACKP_INDEX:
            size = utility.unwrap_int(w_value)
            size = 1 + size - self.stackstart()
            self._stack = [objtable.w_nil] * size
        else:
            # Invalid!
            raise IndexError

    def stackstart(self):
        return constants.MTHDCTX_TEMP_FRAME_START

    # ______________________________________________________________________
    # Method that contains the bytecode for this method/block context

    def w_method(self):
        return self.s_home().w_method()

    def getbytecode(self):
        pc = self.pc()
        bytecode = self.w_method().bytes[pc]
        currentBytecode = ord(bytecode)
        self.store_pc(pc + 1)
        return currentBytecode

    def getNextBytecode(self):
        self.currentBytecode = self.getbytecode()
        return self.currentBytecode

    # ______________________________________________________________________
    # Temporary Variables
    #
    # Are always fetched relative to the home method context.
    
    def gettemp(self, index):
        return self.s_home().gettemp(index)

    def settemp(self, index, w_value):
        self.s_home().settemp(index, w_value)

    # ______________________________________________________________________
    # Stack Manipulation

    def pop(self):
        return self.stack().pop()

    def push(self, w_v):
        assert w_v
        self.stack().append(w_v)

    def push_all(self, lst):
        " Equivalent to 'for x in lst: self.push(x)' where x is a lst "
        assert None not in lst
        self._stack += lst

    def top(self):
        return self.peek(0)
        
    def peek(self, idx):
        return self.stack()[-(idx+1)]

    def pop_n(self, n):
        assert n >= 0
        start = len(self.stack()) - n
        assert start >= 0          # XXX what if this fails?
        del self.stack()[start:]

    def pop_and_return_n(self, n):
        assert n >= 0
        start = len(self.stack()) - n
        assert start >= 0          # XXX what if this fails?
        res = self.stack()[start:]
        del self.stack()[start:]
        return res
    
class W_BlockContext(W_ContextPart):

    def __init__(self, s_home, s_sender, argcnt, initialip):
        W_ContextPart.__init__(self, s_home, s_sender)
        self.argcnt = argcnt
        self._initialip = initialip

    def initialip(self):
        return self._initialip

    def expected_argument_count(self):
        return self.argcnt
        
    def getclass(self):
        from pypy.lang.smalltalk.classtable import w_BlockContext
        return w_BlockContext

    def as_blockcontext_get_shadow(self):
        # Backwards compatibility
        return self
    
    def fetch(self, index):
        from pypy.lang.smalltalk import utility
        if index == constants.BLKCTX_BLOCK_ARGUMENT_COUNT_INDEX:
            return utility.wrap_int(self.argcnt)
        elif index == constants.BLKCTX_INITIAL_IP_INDEX:
            return utility.wrap_int(self.initialip)
        elif index == constants.BLKCTX_HOME_INDEX:
            return self.s_home()
        elif index >= constants.BLKCTX_TEMP_FRAME_START:
            stack_index = len(self.stack()) - index - 1
            return self.stack()[stack_index]
        else:
            return W_ContextPart.fetch(self, index)

    def store(self, index, value):
        # THIS IS ALL UNTESTED CODE and we're a bit unhappy about it
        # because it crashd the translation N+4 times :-(
        from pypy.lang.smalltalk import utility
        if index == constants.BLKCTX_BLOCK_ARGUMENT_COUNT_INDEX:
            self.argcnt = utility.unwrap_int(value)
        elif index == constants.BLKCTX_INITIAL_IP_INDEX:
            self.pc = utility.unwrap_int(value)
        elif index == constants.BLKCTX_HOME_INDEX:
            self._s_home = value.as_methodcontext_get_shadow()
        elif index >= constants.BLKCTX_TEMP_FRAME_START:
            stack_index = len(self.stack()) - index - 1
            self.stack()[stack_index] = value
        else:
            W_ContextPart.store(self, index, value)

    def stackstart(self):
        return constants.BLKCTX_TEMP_FRAME_START

class W_MethodContext(W_ContextPart):
    def __init__(self, w_method, w_receiver,
                 arguments, s_sender=None):
        W_ContextPart.__init__(self, self, s_sender)
        self._w_method = w_method
        self._w_receiver = w_receiver
        self.temps = arguments + [w_nil] * w_method.tempsize

    def as_methodcontext_get_shadow(self):
        # Backwards compatibility
        return self

    def getclass(self):
        from pypy.lang.smalltalk.classtable import w_MethodContext
        return w_MethodContext

    def w_receiver(self):
        return self._w_receiver

    def store_w_receiver(self, w_receiver):
        self._w_receiver = w_receiver

    def fetch(self, index):
        if index == constants.MTHDCTX_METHOD:
            return self.w_method()
        elif index == constants.MTHDCTX_RECEIVER_MAP: # what is this thing?
            return w_nil
        elif index == constants.MTHDCTX_RECEIVER:
            return self._w_receiver
        elif index >= constants.MTHDCTX_TEMP_FRAME_START:
            # First set of indices are temporary variables:
            offset = index - constants.MTHDCTX_TEMP_FRAME_START
            if offset < len(self.temps):
                return self.temps[offset]

            # After that comes the stack:
            offset -= len(self.temps)
            stack_index = len(self.stack()) - offset - 1
            return self.stack()[stack_index]
        else:
            return W_ContextPart.fetch(self, index)

    def store(self, index, w_object):
        if index == constants.MTHDCTX_METHOD:
            self._w_method = w_object
        elif index == constants.MTHDCTX_RECEIVER_MAP: # what is this thing?
            pass
        elif index == constants.MTHDCTX_RECEIVER:
            self._w_receiver = w_object
        elif index >= constants.MTHDCTX_TEMP_FRAME_START:
            # First set of indices are temporary variables:
            offset = index - constants.MTHDCTX_TEMP_FRAME_START
            if offset < len(self.temps):
                self.temps[offset] = w_object

            # After that comes the stack:
            offset -= len(self.temps)
            stack_index = len(self.stack()) - offset - 1
            self.stack()[stack_index] = w_object
        else:
            W_ContextPart.store(self, index, w_object)

    def gettemp(self, idx):
        return self.temps[idx]

    def settemp(self, idx, w_value):
        self.temps[idx] = w_value

    def w_method(self):
        return self._w_method


# Use black magic to create w_nil without running the constructor,
# thus allowing it to be used even in the constructor of its own
# class.  Note that we patch its class in objtable.
w_nil = instantiate(W_PointersObject)
w_nil._vars = []
