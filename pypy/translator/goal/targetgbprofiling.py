import os
import py
import pdb
from pypy.lang.gameboy.profiling.gameboy_profiling_implementation import GameBoyProfilingImplementation


ROM_PATH = str(py.magic.autopath().dirpath().dirpath().dirpath())+"/lang/gameboy/rom"


def entry_point(argv=None):
    if argv is not None and len(argv) > 1:
        filename = argv[1]
    else:
        pos = str(9)
        filename = ROM_PATH+"/rom"+pos+"/rom"+pos+".gb"
    print "loading rom: ", str(filename)
    gameBoy = GameBoyProfilingImplementation()
    try:
        gameBoy.load_cartridge_file(str(filename))
    except:
        print "Corrupt Cartridge"
        gameBoy.load_cartridge_file(str(filename), verify=False)
    try:
        gameBoy.mainLoop()
    except:
        pass
    #pdb.runcall(gameBoy.mainLoop)
    return 0
    

# _____ Define and setup target ___

def target(*args):
    return entry_point, None

def test_target():
    entry_point(["b", ROM_PATH+"/rom9/rom9.gb"])
