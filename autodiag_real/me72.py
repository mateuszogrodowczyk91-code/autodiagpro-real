"""Prawdziwa komunikacja z DME Bosch ME7.2 (BMW E39 540i M62TU) przez kabel K+DCAN (FTDI) w trybie K-line.

Protokół BMW "KWP2000*": [B8][cel 12][źródło F1][długość][dane...][XOR], 9600 baud 8E1, bez inicjalizacji 5-baud.
Źródła: przechwycenia testera na M62TU (pBmwScanner, gigijoe), tabela pomiarów SGBD ME72KWP1,
ten sam kod co w HannaAda (Me72Protocol.cs). NIE ZWERYFIKOWANE jeszcze na TYM aucie.

W tym pliku NIE MA danych przykładowych ani zmyślonych odpowiedzi. Każda liczba pochodzi z bajtów odebranych z DME.
Klasa ISerialLink pozwala testom jednostkowym podać nagrane bajty; aplikacja używa wyłącznie SerialLink (pyserial).
"""
import struct
import time

DME = 0x12
TESTER = 0xF1
HEADER = 0xB8

NRC = {
    0x10: "odmowa ogólna", 0x11: "DME nie zna tej komendy", 0x12: "zły format / podfunkcja nieobsługiwana",
    0x21: "DME zajęte, spróbuj ponownie", 0x22: "warunki niespełnione (np. silnik pracuje / zła sesja)",
    0x31: "parametr poza zakresem", 0x33: "brak dostępu (zabezpieczenie)", 0x78: "odpowiedź w toku",
    0x80: "usługa niedostępna w tej sesji",
}


class DmeError(IOError):
    def __init__(self, msg, tx=b"", rx=b""):
        super().__init__(msg); self.tx = bytes(tx); self.rx = bytes(rx)


class NoResponse(DmeError):
    """Brak odpowiedzi z DME – aplikacja pokazuje 'brak odpowiedzi z DME' zamiast liczb."""


class ProtocolError(DmeError):
    pass


class NegativeResponse(DmeError):
    def __init__(self, sid, code, tx, rx):
        super().__init__("DME odrzuciło komendę 0x%02X: kod 0x%02X = %s" % (sid, code, NRC.get(code, "nieznany kod")), tx, rx)
        self.sid, self.code = sid, code


def xor(data):
    c = 0
    for b in data: c ^= b
    return c


def build(payload, target=DME, source=TESTER):
    body = bytes([HEADER, target, source, len(payload)]) + bytes(payload)
    return body + bytes([xor(body)])


def hexs(b):
    return " ".join("%02X" % x for x in b) if b else "(nic)"


class SerialLink:
    """Prawdziwy port COM (pyserial)."""
    def __init__(self, port):
        import serial
        self.name = port
        self.ser = serial.Serial(port=port, baudrate=9600, bytesize=8, parity=serial.PARITY_EVEN, stopbits=1, timeout=1.0,
                                 xonxoff=False, rtscts=False, dsrdtr=False)
        self.ser.dtr = False; self.ser.rts = False
        self.ser.reset_input_buffer(); self.ser.reset_output_buffer()

    def set_timeout(self, s): self.ser.timeout = s
    def clear(self): self.ser.reset_input_buffer()
    def write(self, b): self.ser.write(b); self.ser.flush()
    def read(self, n): return self.ser.read(n)
    def close(self):
        try: self.ser.close()
        except Exception: pass


def list_ports():
    """Prawdziwa lista portów COM z systemu, z zaznaczeniem kabli FTDI (K+DCAN = VID 0403 PID 6001)."""
    try:
        from serial.tools import list_ports as lp
    except Exception:
        return []
    out = []
    for p in lp.comports():
        ftdi = (p.vid == 0x0403 and p.pid == 0x6001)
        out.append((p.device, "%s%s" % (p.description or "", "  [FTDI – K+DCAN]" if ftdi else "")))
    return out


class Me72Transport:
    REPLY_TIMEOUT = 1.0
    PENDING_TIMEOUT = 5.0
    MAX_PENDING = 20

    def __init__(self, link, trace=None):
        self.link = link; self.trace = trace or (lambda direction, raw, note: None)

    def close(self):
        if self.link: self.link.close(); self.link = None

    def _read_exact(self, n, rx):
        buf = b""
        while len(buf) < n:
            chunk = self.link.read(n - len(buf))
            if not chunk: raise TimeoutError()
            buf += chunk; rx.extend(chunk)
        return buf

    def _read_frame(self, rx, timeout):
        self.link.set_timeout(timeout)
        head = self._read_exact(4, rx)
        tail = self._read_exact(head[3] + 1, rx)
        raw = head + tail
        if xor(raw[:-1]) != raw[-1]:
            raise ProtocolError("Zła suma kontrolna ramki: %s (zły baud/parzystość albo zakłócenia)" % hexs(raw), b"", rx)
        return raw

    def _frame_or_raise(self, rx, timeout, tx, echo, after_pending=False):
        before = len(rx)
        try:
            return self._read_frame(rx, timeout)
        except TimeoutError:
            self.trace("RX-TIMEOUT", bytes(rx), "")
            if after_pending:
                raise NoResponse("Brak odpowiedzi z DME (po 'odpowiedź w toku'). Odebrane: %s" % hexs(rx), tx, rx)
            if not rx:
                raise NoResponse("Brak odpowiedzi z DME: nic nie przyszło – ani echo kabla, ani odpowiedź. "
                                 "Sprawdź: kabel w gnieździe OBD, właściwy port COM, przełącznik kabla w trybie K-line (piny 7+8).", tx, rx)
            if echo and len(rx) == before:
                raise NoResponse("Brak odpowiedzi z DME: kabel działa (wróciło echo), ale DME milczy. "
                                 "Sprawdź: zapłon w pozycji 2 (kontrolki świecą).", tx, rx)
            raise NoResponse("Brak odpowiedzi z DME: przyszły tylko niepełne bajty %s (zły baud/parzystość?)." % hexs(rx), tx, rx)

    def request(self, payload):
        if not self.link: raise NoResponse("Brak odpowiedzi z DME: port nie jest otwarty.")
        tx = build(payload)
        busy = 0
        while True:
            rx = bytearray(); echo = False; pending = 0
            self.link.clear(); self.trace("TX", tx, ""); self.link.write(tx)
            first = self._frame_or_raise(rx, self.REPLY_TIMEOUT, tx, False)
            if first == tx:
                echo = True
                resp = self._frame_or_raise(rx, self.REPLY_TIMEOUT, tx, True)
            else:
                resp = first
            self._check_addr(resp, tx, rx)
            data = resp[4:-1]
            while len(data) >= 3 and data[0] == 0x7F and data[2] == 0x78:
                pending += 1; self.trace("RX", resp, "7F 78 w toku")
                if pending > self.MAX_PENDING: raise ProtocolError("DME ciągle odpowiada 'w toku' – przerwano.", tx, rx)
                resp = self._frame_or_raise(rx, self.PENDING_TIMEOUT, tx, echo, True)
                self._check_addr(resp, tx, rx); data = resp[4:-1]
            if len(data) >= 3 and data[0] == 0x7F and data[2] == 0x21 and busy < 3:
                busy += 1; time.sleep(0.2); continue
            self.trace("RX", resp, "")
            if len(data) >= 3 and data[0] == 0x7F:
                raise NegativeResponse(data[1], data[2], tx, rx)
            if not data:
                raise ProtocolError("Pusta odpowiedź DME.", tx, rx)
            return bytes(data)

    @staticmethod
    def _check_addr(resp, tx, rx):
        if resp[0] != HEADER or resp[1] != TESTER or resp[2] != DME:
            raise ProtocolError("Odpowiedź nie od DME (oczekiwano B8 F1 12 ..): %s" % hexs(resp), tx, rx)


# ------------------------------------------------------------------ dekodowanie (pozycje bajtów z tabeli SGBD ME72KWP1)

def _expect(d, n, head, what):
    if len(d) < n or d[:len(head)] != bytes(head):
        raise ProtocolError("Nieoczekiwana odpowiedź na %s: %s" % (what, hexs(d)))


def u16(d, i): return struct.unpack_from(">H", d, i)[0]
def s16(d, i): return struct.unpack_from(">h", d, i)[0]


def decode_ident(d):
    if d[:1] != b"\xE2": raise ProtocolError("Nieoczekiwana odpowiedź identyfikacji: %s" % hexs(d))
    a = lambda s, e: d[s:e].decode("ascii", "replace").strip("\x00 \xff") if len(d) >= e else "—"
    return {"Numer części BMW": a(1, 8), "Hardware": a(8, 10), "Indeks kodowania": a(10, 12), "Indeks diagnozy": a(12, 14),
            "Indeks magistrali": a(14, 16), "Tydzień produkcji": a(16, 18), "Rok produkcji": a(18, 20), "Dostawca": a(20, 26)}


def decode_engine(d):
    _expect(d, 29, [0x62, 0x40, 0x00], "dane silnika (22 40 00)")
    out = [("Obroty", u16(d, 10) * 0.25, "obr/min"),
           ("Temp. płynu chłodzącego", d[18] * 0.75 - 48, "°C"),
           ("Temp. powietrza dolotowego", d[17] * 0.75 - 48, "°C"),
           ("Prędkość", d[9] * 1.25, "km/h"),
           ("Czas wtrysku", u16(d, 3) * 0.016, "ms"),
           ("Kąt wyprzedzenia zapłonu", struct.unpack_from(">b", d, 19)[0] * 0.75, "°"),
           ("Przepustnica", d[20] * 0.39216, "%"),
           ("Masa powietrza (MAF)", u16(d, 21) * 0.1, "kg/h"),
           ("Moment wskazany", u16(d, 23) * 0.0015259, "%"),
           ("Napięcie akumulatora (DME)", d[25] * 0.095, "V")]
    return out


def decode_roughness(d):
    """22 40 03: nierówność biegu (Laufunruhe) cyl. 1–8 w 1/s. To ten sam sygnał, z którego DME wykrywa wypadanie zapłonów.
    Kolejność względem fizycznych cylindrów NIE potwierdzona na aucie."""
    _expect(d, 19, [0x62, 0x40, 0x03], "nierówność biegu (22 40 03)")
    return [s16(d, 3 + i * 2) * 0.0027756 for i in range(8)]


def decode_adaptations(d):
    _expect(d, 11, [0x62, 0x40, 0x04], "adaptacje (22 40 04)")
    return [("Adaptacja addytywna bank 1", s16(d, 3) * 0.046875, "%"),
            ("Adaptacja addytywna bank 2", s16(d, 5) * 0.046875, "%"),
            ("Adaptacja multiplikatywna bank 1 (skala niepewna)", u16(d, 7) * 0.0000305, "× (1,000 = brak korekty)"),
            ("Adaptacja multiplikatywna bank 2 (skala niepewna)", u16(d, 9) * 0.0000305, "× (1,000 = brak korekty)")]


def decode_lambda_status(d):
    _expect(d, 4, [0x62, 0x40, 0x07], "status lambda (22 40 07)")
    b = d[3]; yn = lambda m: "TAK" if b & m else "NIE"
    return [("Bieg jałowy", yn(0x01), ""), ("Pełne obciążenie", yn(0x02), ""),
            ("Sonda za katalizatorem B2 gotowa", yn(0x04), ""), ("Sonda za katalizatorem B1 gotowa", yn(0x08), ""),
            ("Sonda przed katalizatorem B2 gotowa", yn(0x10), ""), ("Sonda przed katalizatorem B1 gotowa", yn(0x20), ""),
            ("Regulacja lambda B2 aktywna", yn(0x40), ""), ("Regulacja lambda B1 aktywna", yn(0x80), "")]


READ_DTC = [0x18, 0x02, 0xFF, 0xFF]   # ISO 14230 readDTCByStatus; widziane na BMW z ramką B8 – NIEPOTWIERDZONE dla ME7.2
CLEAR_DTC = [0x14, 0xFF, 0x00]        # ISO 14230 clearDiagnosticInformation, wszystkie grupy – NIEPOTWIERDZONE dla ME7.2


def decode_dtc(d):
    if d[:1] != b"\x58": raise ProtocolError("Nieoczekiwana odpowiedź pamięci błędów: %s" % hexs(d))
    count = d[1] if len(d) > 1 else 0
    recs = [(d[i] << 8 | d[i + 1], d[i + 2]) for i in range(2, len(d) - 2, 3)]
    warn = [] if len(recs) == count else ["DME podało %d błędów, w odpowiedzi jest %d pełnych rekordów." % (count, len(recs))]
    return count, recs, warn


class Me72:
    def __init__(self, transport): self.t = transport
    def ident(self): return decode_ident(self.t.request([0xA2]))
    def engine(self): return decode_engine(self.t.request([0x22, 0x40, 0x00]))
    def roughness(self): return decode_roughness(self.t.request([0x22, 0x40, 0x03]))
    def adaptations(self): return decode_adaptations(self.t.request([0x22, 0x40, 0x04]))
    def lambda_status(self): return decode_lambda_status(self.t.request([0x22, 0x40, 0x07]))
    def read_faults(self): return decode_dtc(self.t.request(READ_DTC))

    def clear_faults(self):
        d = self.t.request(CLEAR_DTC)
        if d[:1] != b"\x54": raise ProtocolError("DME nie potwierdziło kasowania: %s" % hexs(d))
        return True


def roughness_outlier(samples, z_thr=3.5, min_samples=5):
    """Średnia nierówność na cylinder + zmodyfikowany z-score (Iglewicz–Hoaglin). Zwraca (średnie, z, indeks|None, opis)."""
    n = len(samples)
    if n == 0: return [None] * 8, [None] * 8, None, "Brak próbek."
    mean = [sum(s[c] for s in samples) / n for c in range(8)]
    med = sorted(mean); med = (med[3] + med[4]) / 2
    dev = sorted(abs(m - med) for m in mean); mad = (dev[3] + dev[4]) / 2
    if n < min_samples: return mean, [None] * 8, None, "Za mało próbek (%d, potrzeba %d)." % (n, min_samples)
    if mad < 1e-9: return mean, [0.0] * 8, None, "Cylindry mają prawie identyczne wartości – brak wyraźnego odstającego."
    z = [0.6745 * (m - med) / mad for m in mean]
    w = max(range(8), key=lambda c: abs(z[c]))
    if abs(z[w]) > z_thr:
        return mean, z, w, "Odstaje pozycja %d (z = %.1f). Potwierdź INPA i zamianą cewki/świecy." % (w + 1, z[w])
    return mean, z, None, "Żaden cylinder wyraźnie nie odstaje (max z = %.1f na pozycji %d)." % (abs(z[w]), w + 1)
