from autodiag_real import modules_ro, ds2

class Fake:
    def __init__(s): s.calls = []
    def request(s, a, d): s.calls.append((a, list(d))); return b"\x01\x02"

def test_scan_rows_readonly_skips_ews():
    f = Fake(); rows = modules_ro.scan_rows(f)
    assert all(d[0] in (ds2.CMD_IDENT, ds2.CMD_FAULTS) and len(d) == 1 for _, d in f.calls)
    assert all(a != 0x44 for a, _ in f.calls)
    assert rows and all(len(r) == 4 for r in rows)


def test_dme_clear_sends_14ff00_and_needs_54():
    from autodiag_real import me72
    import pytest
    class T:
        def __init__(s, r): s.r = r; s.sent = []
        def request(s, d): s.sent.append(list(d)); return s.r
    t = T(b"\x54\xff\x00"); assert me72.Me72(t).clear_faults() is True and t.sent == [[0x14, 0xFF, 0x00]]
    with pytest.raises(me72.DmeError): me72.Me72(T(b"\x7f\x14\x22")).clear_faults()
