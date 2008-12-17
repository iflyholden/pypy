import py
from pypy.rpython.test.tool import LLRtypeMixin, OORtypeMixin
from pypy.jit.hintannotator.policy import HintAnnotatorPolicy
from pypy.jit.rainbow.test.test_interpreter import InterpretationTest, P_OOPSPEC
from pypy.jit.rainbow.test.test_interpreter import OOTypeMixin
from pypy.rlib.jit import hint



class VListTest(InterpretationTest):

    def test_vlist(self):
        def ll_function():
            lst = []
            lst.append(12)
            return lst[0]
        res = self.interpret(ll_function, [], [], policy=P_OOPSPEC)
        assert res == 12
        self.check_insns({})

    def test_fixed_vlist(self):
        def ll_function(flag):
            lst = [0, 0, 0]
            if flag:
                lst[0] = 42
            else:
                lst[0] = 1
            return lst[0]
        res = self.interpret(ll_function, [True], [], policy=P_OOPSPEC)
        assert res == 42
        self.check_insns({})

    def test_enter_block(self):
        def ll_function(flag):
            lst = []
            lst.append(flag)
            lst.append(131)
            if flag:
                return lst[0]
            else:
                return lst[1]
        res = self.interpret(ll_function, [6], [], policy=P_OOPSPEC)
        assert res == 6
        self.check_insns({'int_is_true': 1})
        res = self.interpret(ll_function, [0], [], policy=P_OOPSPEC)
        assert res == 131
        self.check_insns({'int_is_true': 1})

    def test_merge(self):
        def ll_function(flag):
            lst = []
            if flag:
                lst.append(flag)
            else:
                lst.append(131)
            return lst[-1]
        res = self.interpret(ll_function, [6], [], policy=P_OOPSPEC)
        assert res == 6
        self.check_insns({'int_is_true': 1})
        res = self.interpret(ll_function, [0], [], policy=P_OOPSPEC)
        assert res == 131
        self.check_insns({'int_is_true': 1})

    def test_replace(self):
        def ll_function(flag):
            lst = []
            if flag:
                lst.append(12)
            else:
                lst.append(131)
            return lst[-1]
        res = self.interpret(ll_function, [6], [], policy=P_OOPSPEC)
        assert res == 12
        self.check_insns({'int_is_true': 1})
        res = self.interpret(ll_function, [0], [], policy=P_OOPSPEC)
        assert res == 131
        self.check_insns({'int_is_true': 1})

    def test_force(self):
        def ll_function(n):
            lst = []
            lst.append(n)
            if n:
                lst.append(12)
            return lst[-1]
        res = self.interpret(ll_function, [6], [], policy=P_OOPSPEC)
        assert res == 12
        res = self.interpret(ll_function, [0], [], policy=P_OOPSPEC)
        assert res == 0

    force_fixed_insns = None
    def test_force_fixed(self):
        def ll_function(flag):
            lst = [0, 0, 0]
            if flag:
                lst[0] = 42
            else:
                lst[0] = 1
            return lst
        res = self.interpret(ll_function, [True], [], policy=P_OOPSPEC)
        res = self.ll_to_list(res)
        assert res == [42, 0, 0]
        self.check_insns(self.force_fixed_insns)

    def test_oop_vlist(self):
        def ll_function():
            lst = [3, 5]
            five = lst.pop()        # [3]
            lst.append(len(lst))    # [3, 1]
            lst2 = list(lst)
            three = lst.pop(0)      # [1]
            lst.insert(0, 8)        # [8, 1]
            lst.insert(2, 7)        # [8, 1, 7]
            lst.append(not lst)     # [8, 1, 7, 0]
            lst.reverse()           # [0, 7, 1, 8]
            lst3 = lst2 + lst       # [3, 1, 0, 7, 1, 8]
            del lst3[1]             # [3, 0, 7, 1, 8]
            seven = lst3.pop(2)     # [3, 0, 1, 8]
            lst3[0] = 9             # [9, 0, 1, 8]
            nine = lst3.pop(-4)     # [0, 1, 8]
            return (len(lst3) * 10000000 +
                    lst3[0]   *  1000000 +
                    lst3[1]   *   100000 +
                    lst3[-1]  *    10000 +
                    five      *     1000 +
                    three     *      100 +
                    seven     *       10 +
                    nine      *        1)
        assert ll_function() == 30185379
        res = self.interpret(ll_function, [], [], policy=P_OOPSPEC)
        assert res == 30185379
        self.check_insns({})

    def test_alloc_and_set(self):
        def ll_function():
            lst = [0] * 9
            return len(lst)
        res = self.interpret(ll_function, [], [], policy=P_OOPSPEC)
        assert res == 9
        self.check_insns({})
        
    def test_lists_deepfreeze(self):
        l1 = [1,2,3,4,5]
        l2 = [6,7,8,9,10]
        def getlist(n):
            if n:
                return l1
            else:
                return l2
        def ll_function(n, i):
            l = getlist(n)
            l = hint(l, deepfreeze=True)
            res = l[i]
            res = hint(res, variable=True)
            return res
        
        res = self.interpret(ll_function, [3, 4], [0, 1], policy=P_OOPSPEC)
        assert res == 5
        self.check_insns({})

    def test_frozen_list(self):
        lst = [5, 7, 9]
        def ll_function(x):
            mylist = hint(lst, deepfreeze=True)
            z = mylist[x]
            hint(z, concrete=True)
            return z

        res = self.interpret(ll_function, [1], policy=P_OOPSPEC)
        assert res == 7
        self.check_insns({})

    def test_frozen_list_indexerror(self):
        lst = [5, 7, 9]
        def ll_function(x):
            mylist = hint(lst, deepfreeze=True)
            try:
                z = mylist[x]
            except IndexError:
                return -42
            hint(z, concrete=True)
            return z

        res = self.interpret(ll_function, [4], policy=P_OOPSPEC)
        assert res == -42
        self.check_insns({})

    def test_bogus_index_while_compiling(self):
        class Y:
            pass

        def g(lst, y, n):
            lst = hint(lst, deepfreeze=True)
            if y.flag:
                return lst[n]
            else:
                return -7

        y = Y()
        lst1 = [3, 4, 5]
        lst2 = [6, 2]

        def h(i):
            if i == 1: return lst1
            elif i == 2: return lst2
            else: return []

        def f(n):
            y.flag = n < 3
            g(h(1), y, n)
            y.flag = n < 2
            return g(h(2), y, n)

        res = self.interpret(f, [2], [0], policy=P_OOPSPEC)
        assert res == -7

    def test_vlist_of_vlist(self):
        py.test.skip('infinite loop')
        def fn(n):
            stack = []
            for i in range(n):
                mylist = []
                for j in range(i, n):
                    mylist.append(j)
                stack.append(mylist)
            mylist = stack.pop()
            return mylist[0]
        res = self.interpret(fn, [10], [], policy=P_OOPSPEC)
        assert res == 9
        self.check_insns({})

class TestOOType(OOTypeMixin, OORtypeMixin, VListTest):
    type_system = "ootype"
    force_fixed_insns = {'oonewarray': 1, 'oosend': 3}

class TestLLType(LLRtypeMixin, VListTest):
    type_system = "lltype"
    force_fixed_insns = {'direct_call': 4}
