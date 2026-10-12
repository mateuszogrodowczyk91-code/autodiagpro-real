import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import pytest
import android_bridge as ab, elm327
from autodiag_real import me72


def test_offline_everything_dash():
    ab.detach()
    for f in (ab.faults, ab.live_data, ab.cold_start, ab.modules):
        t = f(); assert "brak połączenia" in t
    assert "—" in ab.live_data() and "—" in ab.faults()


class FakeJ:
    def __init__(self): self.w = []
    def getName(self): return "fake"
    def setTimeout(self, s): pass
    def clear(self): pass
    def write(self, b): self.w.append(b)
    def read(self, n): return b""
    def close(self): pass


def test_write_commands_blocked():
    t = ab.ReadOnlyTransport(ab.JavaLink(FakeJ()))
    for p in (me72.CLEAR_DTC, [0x34, 0, 0], [0x3B, 1], [0x27, 1], [0x31, 1], [0x2E, 1]):
        with pytest.raises(ab.WriteBlocked): t.request(p)
    with pytest.raises(ab.WriteBlocked): ab.blocked("EWS")


def test_kline_no_answer_is_dash():
    j = FakeJ(); ab.attach_kline(j)
    assert "—" in ab.live_data() and "Brak odpowiedzi" in ab.faults()
    assert j.w and j.w[0][0] == 0xB8   # prawdziwa ramka wysłana
    ab.detach()


def test_elm_parsers():
    assert elm327.parse_pid(["41 05 5A"], "05") == [0x5A]
    assert elm327.parse_mode03(["43 01 33 00 00 00 00"]) == ["P0133"]
    assert elm327.parse_mode03(["43 02 01 71 03 00"]) == ["P0171", "P0300"]


def test_elm_mode04_blocked():
    e = elm327.Elm327(None)
    with pytest.raises(elm327.ElmError): e.cmd("04")
    assert "brak połączenia" in e.faults_report() and "—" in e.live_report()
