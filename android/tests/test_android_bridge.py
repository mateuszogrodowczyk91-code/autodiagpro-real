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
    # nawet z allow_clear przepuszczane jest tylko dokładnie 14 FF 00
    for p in ([0x34, 0, 0], [0x3B, 1], [0x27, 1], [0x14, 0x00, 0x00]):
        with pytest.raises(ab.WriteBlocked): t.request(p, allow_clear=True)


def test_clear_needs_confirmation_and_link():
    ab.detach()
    with pytest.raises(ab.WriteBlocked): ab.clear_faults()
    assert "brak połączenia" in ab.clear_faults(True)
    j = FakeJ(); ab.attach_kline(j)
    assert "NIE wykonano" in ab.clear_faults(True)
    assert j.w[-1] == me72.build(me72.CLEAR_DTC)   # B8 12 F1 03 14 FF 00 XOR
    assert "silnik ZGASZONY" in ab.clear_warning() and "NIE jest jeszcze zweryfikowana" in ab.clear_warning()
    ab.detach()


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
    with pytest.raises(elm327.ElmError): e.clear_faults()
    assert "brak połączenia" in e.clear_faults(True)
    with pytest.raises(elm327.ElmError): e.cmd("02", allow_clear=True)
    assert "brak połączenia" in e.faults_report() and "—" in e.live_report()


class ElmFake:
    """Symulator protokołu do testu (nie dane auta): pierwsze 'dead' odpowiedzi puste, potem echo 'OK'."""
    def __init__(self, dead=0, at2="OK"): self.dead, self.at2, self.sent, self.rec = dead, at2, [], 0
    def write(self, b): self.sent.append(b.decode().strip())
    def readUntilPrompt(self, t):
        if self.dead: self.dead -= 1; return ""
        return self.at2 if self.sent[-1] == "ATAT2" else "OK"
    def reconnect(self): self.rec += 1; return True


def test_elm_adaptive_and_fallback():
    j = ElmFake(at2="?"); e = elm327.Elm327(j); e.init()
    assert e.ok and "ATAT1" in j.sent and "ATST64" in j.sent and e.rtt is not None
    assert 1.0 <= e.timeout_for(5.0) <= 5.0


def test_elm_reconnect_once():
    j = ElmFake(); e = elm327.Elm327(j); e.init(); j.dead = 2
    assert e.keepalive() == "OK" and j.rec == 1
    j.dead = 10
    assert e.keepalive() == "—"


def test_elm_clear_never_retried():
    j = ElmFake(); e = elm327.Elm327(j); e.init(); j.dead = 5
    assert "NIE wykonano" in e.clear_faults(True) and j.rec == 0
