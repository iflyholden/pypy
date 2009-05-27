from pypy.lang.io.parserhack import parse, interpret
from pypy.lang.io.model import W_List, W_Number
import py.test


def test_parse_empty_list():
    inp = "a := list()\na"
    res,space = interpret(inp)
    assert isinstance(res, W_List)
    assert res.items == []
    
def test_parse_list():
    inp = "a := list(1,2,3)\na"
    res,space = interpret(inp)
    assert isinstance(res, W_List)
    assert res.items == [W_Number(space, 1), W_Number(space, 2), W_Number(space, 3)]
    
def test_list_proto():
    inp = "a := list(1,2,3)\na"
    res,space = interpret(inp)
    assert isinstance(res, W_List)
    assert res.protos == [space.w_list]
    assert space.w_list.protos == [space.w_object]

def test_list_append():
    inp = "a := list(); a append(1)"
    res,space = interpret(inp)
    assert res.items == [W_Number(space, 1)]

def test_list_append_multiple():
    inp = "a := list(1,2); a append(3,4,5)"
    res,space = interpret(inp)
    assert res.items == [W_Number(space, 1), 
                            W_Number(space, 2),
                            W_Number(space, 3),
                            W_Number(space, 4),
                            W_Number(space, 5)]
    
def test_list_at():
    inp = "a := list(1,2,3); a at(2)"
    res,space = interpret(inp)
    assert res.value == 3
    
def test_list_at_out_of_range_is_nil():
    inp = "a := list(1,2,3); a at(1234)"
    res,space = interpret(inp)
    assert res == space.w_nil
    
def test_list_at_requires_arg():
    inp = "a := list(1,2,3); a at()"
    # Unspecified exception until error handling are introduced
    assert py.test.raises(Exception, 'interpret(inp)')

def test_list_at_requires_numeric_arg():
    inp = 'a := list(1,2,3); a at("2")'
    # Unspecified exception until error handling are introduced
    assert py.test.raises(Exception, 'interpret(inp)')
    
def test_list_foreach_key_value_returns_last():
    inp = 'a := list(1, 2, 3); a foreach(key, value, key+value)'
    res,space = interpret(inp)
    assert res.value == 5
    
def test_list_foreach_value_returns_last():
    inp = 'c := 99; a := list(1, 2, 3); a foreach(value, c)'
    res,space = interpret(inp)
    assert res.value == 99
    
def test_list_foreach_wo_args_returns_last():
    inp = 'c := 99; a := list(1, 2, 3); a foreach(c)'
    res,space = interpret(inp)
    assert res.value == 99
        
def test_list_key_value():
    inp = 'b := list(); a := list(99, 34); a foreach(key, value, b append(list(key, value))); b'
    res,space = interpret(inp)
    value = [(x.items[0].value, x.items[1].value) for x in res.items]
    assert value == [(0, 99), (1, 34)]
    
def test_list_foreach_leaks_variables():
    inp = 'b := list(); a := list(99, 34); a foreach(key, value, b append(list(key, value))); key+value'
    res,space = interpret(inp)
    assert res.value == 35