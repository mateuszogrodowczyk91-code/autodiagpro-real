from autodiag_real import modules_ro, ds2

class Fake:
    def __init__(s): s.calls = []
    def request(s, a, d): s.calls.append((a, list(d))); return b"\x01\x02"

def test_scan_rows_readonly_skips_ews():
    f = Fake(); rows = modules_ro.scan_rows(f)
    assert all(d[0] in (ds2.CMD_IDENT, ds2.CMD_FAULTS) and len(d) == 1 for _, d in f.calls)
    assert all(a != 0x44 for a, _ in f.calls)
    assert rows and all(len(r) == 4 for r in rows)
