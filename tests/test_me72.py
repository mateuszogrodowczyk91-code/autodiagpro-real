"""Testy protokołu. Atrapa łącza (FakeLink) istnieje WYŁĄCZNIE tutaj – aplikacja jej nie importuje."""
import os, sys, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from autodiag_real import me72


class FakeLink:
    def __init__(self, replies, echo=True):
        self.replies = list(replies); self.echo = echo; self.buf = b""; self.sent = []
    def set_timeout(self, s): pass
    def clear(self): self.buf = b""
    def write(self, b):
        self.sent.append(bytes(b)); self.buf += (bytes(b) if self.echo else b"")
        if self.replies: self.buf += self.replies.pop(0)
    def read(self, n): out, self.buf = self.buf[:n], self.buf[n:]; return out
    def close(self): pass


def reply(payload): return me72.build(payload, target=me72.TESTER, source=me72.DME)


def dev(*payloads, echo=True): return me72.Me72(me72.Me72Transport(FakeLink([reply(p) for p in payloads], echo)))


def test_frame_known_example():
    assert me72.build([0xA2]) == bytes.fromhex("b812f101a2f8")


def test_ident_with_and_without_echo():
    p = b"\xE2" + b"7545105" + b"02" + b"05" + b"0B" + b"03" + b"28" + b"01" + b"BOSCH "
    for e in (True, False):
        i = dev(p, echo=e).ident()
        assert i["Numer części BMW"] == "7545105" and i["Dostawca"] == "BOSCH"


def test_engine_decode():
    d = bytearray(29); d[0:3] = b"\x62\x40\x00"; d[10:12] = (3200).to_bytes(2, "big"); d[18] = int((90 + 48) / 0.75); d[25] = 147
    v = {n: x for n, x, _ in dev(bytes(d)).engine()}
    assert v["Obroty"] == 800 and abs(v["Temp. płynu chłodzącego"] - 90) < 0.5 and abs(v["Napięcie akumulatora (DME)"] - 13.97) < 0.01


def test_roughness_and_outlier():
    d = bytearray(19); d[0:3] = b"\x62\x40\x03"
    vals = [10, 12, 9, 11, 400, 10, 12, 11]
    for i, x in enumerate(vals): d[3 + i * 2:5 + i * 2] = x.to_bytes(2, "big", signed=True)
    r = dev(bytes(d)).roughness(); assert abs(r[4] - 400 * 0.0027756) < 1e-9
    mean, z, idx, _ = me72.roughness_outlier([r] * 20); assert idx == 4


def test_dtc_parse_and_clear():
    count, recs, warn = dev(bytes([0x58, 2, 0x00, 0x27, 0x24, 0x00, 0x32, 0x20])).read_faults()
    assert count == 2 and recs == [(0x0027, 0x24), (0x0032, 0x20)] and not warn
    assert dev(bytes([0x54, 0xFF, 0x00])).clear_faults()


def test_no_cable_gives_no_response():
    t = me72.Me72Transport(FakeLink([], echo=False))
    with pytest.raises(me72.NoResponse, match="brak odpowiedzi z DME|Brak odpowiedzi z DME"): me72.Me72(t).ident()


def test_echo_only_means_dme_silent():
    with pytest.raises(me72.NoResponse, match="DME milczy"): me72.Me72(me72.Me72Transport(FakeLink([], echo=True))).ident()


def test_negative_and_pending():
    with pytest.raises(me72.NegativeResponse): dev(bytes([0x7F, 0x18, 0x11])).read_faults()
    t = me72.Me72Transport(FakeLink([reply(bytes([0x7F, 0x18, 0x78])) + reply(bytes([0x58, 0]))]))
    assert me72.Me72(t).read_faults() == (0, [], [])


def test_bad_checksum():
    bad = bytearray(reply(b"\xE2abc")); bad[-1] ^= 0xFF
    with pytest.raises(me72.ProtocolError): me72.Me72(me72.Me72Transport(FakeLink([bytes(bad)]))).ident()


def test_app_has_no_demo_or_simulator():
    src = open(os.path.join(os.path.dirname(__file__), "..", "autodiag_real", "app.py"), encoding="utf-8").read().lower()
    src += open(os.path.join(os.path.dirname(__file__), "..", "autodiag_real", "me72.py"), encoding="utf-8").read().lower()
    for bad in ("random", "fakelink", "simulatortransport", "simulator.json", "import tests"):
        assert bad not in src


def test_no_demo_strings_anywhere_in_app():
    root = os.path.join(os.path.dirname(__file__), "..", "autodiag_real")
    bad = ("tryb demo", "simulator", "symulator", "random", "psutil", "cpu_percent", "virtual_memory", "qrcode", "firestore", "googleapis", "misfire_cyl")
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".py"):
                s = open(os.path.join(dp, f), encoding="utf-8").read().lower()
                for b in bad: assert b not in s, (f, b)
