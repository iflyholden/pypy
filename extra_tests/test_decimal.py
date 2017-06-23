import pickle
import sys

from support import import_fresh_module

C = import_fresh_module('decimal', fresh=['_decimal'])
P = import_fresh_module('decimal', blocked=['_decimal'])
# import _decimal as C
# import _pydecimal as P

def test_C():
    sys.modules["decimal"] = C
    import decimal
    d = decimal.Decimal('1')
    assert isinstance(d, C.Decimal)
    assert isinstance(d, decimal.Decimal)
    assert isinstance(d.as_tuple(), C.DecimalTuple)

    assert d == C.Decimal('1')

def check_round_trip(val, proto):
    d = C.Decimal(val)
    p = pickle.dumps(d, proto)
    assert d == pickle.loads(p)

def test_pickle():
    v = '-3.123e81723'
    for proto in range(pickle.HIGHEST_PROTOCOL + 1):
        sys.modules["decimal"] = C
        check_round_trip('-3.141590000', proto)
        check_round_trip(v, proto)

        cd = C.Decimal(v)
        pd = P.Decimal(v)
        cdt = cd.as_tuple()
        pdt = pd.as_tuple()
        assert cdt.__module__ == pdt.__module__

        p = pickle.dumps(cdt, proto)
        r = pickle.loads(p)
        assert isinstance(r, C.DecimalTuple)
        assert cdt == r

        sys.modules["decimal"] = C
        p = pickle.dumps(cd, proto)
        sys.modules["decimal"] = P
        r = pickle.loads(p)
        assert isinstance(r, P.Decimal)
        assert r == pd

        sys.modules["decimal"] = C
        p = pickle.dumps(cdt, proto)
        sys.modules["decimal"] = P
        r = pickle.loads(p)
        assert isinstance(r, P.DecimalTuple)
        assert r == pdt
