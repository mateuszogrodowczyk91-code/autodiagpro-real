import pytest
from autodiag_real import live, modules_ro, ds2, me72
from test_ds2 import Link, fr


def test_live_offline_no_values():
    rows, _, ok = live.snapshot(None)
    assert not ok and rows and all(r[1] == "—" and r[3] == "brak połączenia" for r in rows)


class FailDme:
    def __getattr__(self, n):
        def f(): raise me72.NoResponse("Brak odpowiedzi z DME. x")
        return f


def test_live_no_response():
    rows, _, ok = live.snapshot(FailDme())
    assert not ok and all(r[1] == "—" for r in rows)


def test_live_engine_real_bytes():
    d = bytearray(29); d[0:3] = b"\x62\x40\x00"; d[10:12] = (3200).to_bytes(2, "big"); d[18] = 100
    class D:
        def engine(s): return me72.decode_engine(bytes(d))
        def roughness(s): raise me72.NoResponse("x")
        def lambda_status(s): raise me72.NoResponse("x")
    rows, _, ok = live.snapshot(D())
    assert ok and ("Obroty", 800.0, "obr/min", "OK") in rows


def test_readonly_blocks_writes():
    ro = modules_ro.ReadOnlyDs2(ds2.Ds2(Link([])))
    for cmd in ([0x05], [0x0C, 1], [0x08], [0x00, 1], []):
        with pytest.raises(modules_ro.WriteBlocked): ro.request(0x32, cmd)
    with pytest.raises(modules_ro.WriteBlocked): ro.request(modules_ro.EWS_ADDR, [0x00])


def test_readonly_read_module():
    ro = modules_ro.ReadOnlyDs2(ds2.Ds2(Link([fr(0x32, [0xA0, 1, 2]), fr(0x32, [0xA0])])))
    r = ro.read_module("EGS", 0x32)
    assert r["identyfikacja"] == "01 02" and r["błędy (surowo)"] == "(nic)" and r["status"] == "OK"


def test_offline_table():
    t = modules_ro.offline_table()
    assert t and all(x["status"] == "brak połączenia" and x["identyfikacja"] == "—" for x in t)
