"""DS2 (K-line, 9600 8E1) – inne moduły E39. Tylko ODCZYT: identyfikacja (00) i pamięć błędów (04).
Ramka: [adres, długość całej ramki, dane..., XOR]. Odpowiedź: [adres, długość, A0=OK / A1/A2=odmowa, dane..., XOR].
Dane pokazywane surowo (hex) – bez plików SGBD nie zgadujemy znaczenia bajtów."""
from .me72 import xor, hexs, NoResponse, ProtocolError

MODULES = [("EGS – skrzynia automatyczna", 0x32), ("ABS/ASC/DSC", 0x56), ("Airbag (MRS)", 0xA4), ("IKE – zegary", 0x80),
           ("LCM – światła", 0xD0), ("EHC – zawieszenie pneumatyczne", 0xAC), ("IHKA – klimatyzacja", 0x5B), ("GM – moduł ogólny", 0x00)]
CMD_IDENT, CMD_FAULTS = 0x00, 0x04


def build(addr, data):
    body = bytes([addr, len(data) + 3]) + bytes(data)
    return body + bytes([xor(body)])


class Ds2:
    TIMEOUT = 1.0

    def __init__(self, link, trace=None):
        self.link = link; self.trace = trace or (lambda d, r, n: None)

    def _frame(self, rx):
        self.link.set_timeout(self.TIMEOUT)
        h = self.link.read(2); rx.extend(h)
        if len(h) < 2: raise TimeoutError()
        if h[1] < 3: raise ProtocolError("Zła długość ramki DS2: %s" % hexs(rx), b"", rx)
        t = self.link.read(h[1] - 2); rx.extend(t)
        if len(t) < h[1] - 2: raise TimeoutError()
        raw = bytes(h + t)
        if xor(raw[:-1]) != raw[-1]: raise ProtocolError("Zła suma DS2: %s" % hexs(raw), b"", rx)
        return raw

    def request(self, addr, data):
        if not self.link: raise NoResponse("Port nie jest otwarty.")
        lock = getattr(self.link, "lock", None)
        if lock is None: return self._request(addr, data)
        with lock: return self._request(addr, data)

    def _request(self, addr, data):
        tx = build(addr, data); rx = bytearray(); self.link.clear(); self.trace("TX", tx, "DS2"); self.link.write(tx)
        try:
            r = self._frame(rx)
            if r == tx: r = self._frame(rx)
        except TimeoutError:
            raise NoResponse("Moduł 0x%02X nie odpowiada (nie ma go w aucie, zapłon wył. albo inna linia diagnostyczna). Odebrane: %s" % (addr, hexs(rx)), tx, rx)
        self.trace("RX", r, "DS2")
        if r[0] != addr: raise ProtocolError("Odpowiedź od innego adresu: %s" % hexs(r), tx, rx)
        if len(r) < 4 or r[2] != 0xA0: raise ProtocolError("Moduł odmówił (status %s)" % ("%02X" % r[2] if len(r) > 2 else "?"), tx, rx)
        return r[3:-1]

    def ident(self, addr): return self.request(addr, [CMD_IDENT])
    def faults(self, addr): return self.request(addr, [CMD_FAULTS])

    def scan(self):
        out = []
        for name, a in MODULES:
            row = [name, "0x%02X" % a]
            for fn in (self.ident, self.faults):
                try: row.append(hexs(fn(a)))
                except Exception as e: row.append("— " + str(e).split(".")[0])
            out.append(row)
        return out
