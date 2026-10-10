from autodiag_real import ds2
from autodiag_real.me72 import xor

class Link:
    def __init__(s, replies): s.buf = b""; s.replies = replies
    def set_timeout(s, t): pass
    def clear(s): pass
    def write(s, b): s.buf += b + s.replies.pop(0)
    def read(s, n): r, s.buf = s.buf[:n], s.buf[n:]; return r

def fr(a, d): b = bytes([a, len(d) + 3]) + bytes(d); return b + bytes([xor(b)])

def test_build(): assert ds2.build(0x32, [0]) == bytes([0x32, 4, 0, 0x32 ^ 4])
def test_ident_with_echo():
    l = Link([fr(0x32, [0xA0, 1, 2])]); d = ds2.Ds2(l)
    assert d.ident(0x32) == bytes([1, 2])
def test_no_reply():
    d = ds2.Ds2(Link([b""]))
    try: d.ident(0x56); assert False
    except ds2.NoResponse: pass
def test_refused():
    d = ds2.Ds2(Link([fr(0x56, [0xA2])]))
    try: d.faults(0x56); assert False
    except ds2.ProtocolError: pass
