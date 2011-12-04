import py
import errno, os, StringIO
from pypy.tool.sourcetools import func_with_new_name
from pypy.rpython.lltypesystem import rffi
from pypy.translator.sandbox.sandlib import SandboxedProc
from pypy.translator.sandbox.sandlib import SimpleIOSandboxedProc
from pypy.translator.sandbox.sandlib import VirtualizedSandboxedProc
from pypy.translator.sandbox.sandlib import VirtualizedSocketProc
from pypy.translator.sandbox.test.test_sandbox import compile
from pypy.translator.sandbox.vfs import Dir, File


class MockSandboxedProc(SandboxedProc):
    """A sandbox process wrapper that replays expected syscalls."""

    def __init__(self, args, expected):
        SandboxedProc.__init__(self, args)
        self.expected = expected
        self.seen = 0

    def _make_method(name):
        def do_xxx(self, *input):
            print "decoded from subprocess: %s%r" % (name, input)
            expectedmsg, expectedinput, output = self.expected[self.seen]
            assert name == expectedmsg
            assert input == expectedinput
            self.seen += 1
            if isinstance(output, Exception):
                raise output
            return output
        return func_with_new_name(do_xxx, 'do_%s' % name)

    do_ll_os__ll_os_open  = _make_method("open")
    do_ll_os__ll_os_read  = _make_method("read")
    do_ll_os__ll_os_write = _make_method("write")
    do_ll_os__ll_os_close = _make_method("close")


def test_lib():
    def entry_point(argv):
        fd = os.open("/tmp/foobar", os.O_RDONLY, 0777)
        assert fd == 77
        res = os.read(fd, 123)
        assert res == "he\x00llo"
        count = os.write(fd, "world\x00!\x00")
        assert count == 42
        for arg in argv:
            count = os.write(fd, arg)
            assert count == 61
        os.close(fd)
        return 0
    exe = compile(entry_point)

    proc = MockSandboxedProc([exe, 'x1', 'y2'], expected = [
        ("open", ("/tmp/foobar", os.O_RDONLY, 0777), 77),
        ("read", (77, 123), "he\x00llo"),
        ("write", (77, "world\x00!\x00"), 42),
        ("write", (77, exe), 61),
        ("write", (77, "x1"), 61),
        ("write", (77, "y2"), 61),
        ("close", (77,), None),
        ])
    proc.handle_forever()
    assert proc.seen == len(proc.expected)

def test_foobar():
    py.test.skip("to be updated")
    foobar = rffi.llexternal("foobar", [rffi.CCHARP], rffi.LONG)
    def entry_point(argv):
        s = rffi.str2charp(argv[1]); n = foobar(s); rffi.free_charp(s)
        s = rffi.str2charp(argv[n]); n = foobar(s); rffi.free_charp(s)
        return n
    exe = compile(entry_point)

    proc = MockSandboxedProc([exe, 'spam', 'egg'], expected = [
        ("foobar", ("spam",), 2),
        ("foobar", ("egg",), 0),
        ])
    proc.handle_forever()
    assert proc.seen == len(proc.expected)

def test_simpleio():
    def entry_point(argv):
        print "Please enter a number:"
        buf = ""
        while True:
            t = os.read(0, 1)    # 1 character from stdin
            if not t:
                raise EOFError
            if t == '\n':
                break
            buf += t
        num = int(buf)
        print "The double is:", num * 2
        return 0
    exe = compile(entry_point)

    proc = SimpleIOSandboxedProc([exe, 'x1', 'y2'])
    output, error = proc.communicate("21\n")
    assert output == "Please enter a number:\nThe double is: 42\n"
    assert error == ""

def test_socketio():
    class SocketProc(VirtualizedSocketProc, SimpleIOSandboxedProc):
        def build_virtual_root(self):
            pass
    
    def entry_point(argv):
        fd = os.open("tcp://codespeak.net:80", os.O_RDONLY, 0777)
        os.write(fd, 'GET /\n')
        print os.read(fd, 30)
        return 0
    exe = compile(entry_point)

    proc = SocketProc([exe])
    output, error = proc.communicate("")
    assert output.startswith('<!DOCTYPE')

def test_oserror():
    def entry_point(argv):
        try:
            os.open("/tmp/foobar", os.O_RDONLY, 0777)
        except OSError, e:
            os.close(e.errno)    # nonsense, just to see outside
        return 0
    exe = compile(entry_point)

    proc = MockSandboxedProc([exe], expected = [
        ("open", ("/tmp/foobar", os.O_RDONLY, 0777), OSError(-42, "baz")),
        ("close", (-42,), None),
        ])
    proc.handle_forever()
    assert proc.seen == len(proc.expected)


class SandboxedProcWithFiles(VirtualizedSandboxedProc, SimpleIOSandboxedProc):
    """A sandboxed process with a simple virtualized filesystem.

    For testing file operations.

    """
    def build_virtual_root(self):
        return Dir({
            'hi.txt': File("Hello, world!\n"),
             })

def test_too_many_opens():
    def entry_point(argv):
        try:
            open_files = []
            for i in range(500):
                fd = os.open('/hi.txt', os.O_RDONLY, 0777)
                open_files.append(fd)
                txt = os.read(fd, 100)
                if txt != "Hello, world!\n":
                    print "Wrong content: %s" % txt
        except OSError, e:
            if e.errno != errno.EMFILE:
                print "OSError: %s!" % (e.errno,)
        else:
            print "We opened 500 files! Shouldn't have been able to."
        print "All ok!"
        return 0
    exe = compile(entry_point)

    proc = SandboxedProcWithFiles([exe])
    output, error = proc.communicate("")
    assert output == "All ok!\n"
    assert error == ""
