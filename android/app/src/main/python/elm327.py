"""ELM327 przez Bluetooth – tylko standardowe OBD-II (SAE J1979), tylko silnik. TYLKO ODCZYT (tryby 01 i 03; tryb 04 kasowania zablokowany).
W E39 ELM327 nie widzi pozostałych modułów BMW – do tego potrzebny kabel K+DCAN.
Obiekt Java: write(byte[]), readUntilPrompt(timeout_s) -> str. Bez połączenia: "—" / "brak połączenia"."""
NO_LINK = "brak połączenia"
DASH = "—"
ALLOWED_PREFIX = ("AT", "01", "03")

PIDS = [("0C", "Obroty", "obr/min", lambda b: (b[0] * 256 + b[1]) / 4.0),
        ("05", "Temp. płynu chłodzącego", "°C", lambda b: b[0] - 40),
        ("0F", "Temp. powietrza dolotowego", "°C", lambda b: b[0] - 40),
        ("0D", "Prędkość", "km/h", lambda b: b[0]),
        ("11", "Przepustnica", "%", lambda b: b[0] * 100 / 255.0),
        ("0E", "Kąt wyprzedzenia zapłonu", "°", lambda b: b[0] / 2.0 - 64),
        ("10", "Masa powietrza (MAF)", "g/s", lambda b: (b[0] * 256 + b[1]) / 100.0),
        ("04", "Obciążenie silnika", "%", lambda b: b[0] * 100 / 255.0)]


class ElmError(IOError):
    pass


def clean(resp):
    return [l.strip() for l in resp.replace("\r", "\n").replace(">", "").split("\n")
            if l.strip() and not l.strip().upper().startswith(("SEARCHING", "BUS INIT"))]


def hex_bytes(line):
    s = line.replace(" ", "")
    if len(s) % 2: raise ElmError("Nieparzysta odpowiedź: %s" % line)
    return [int(s[i:i + 2], 16) for i in range(0, len(s), 2)]


def parse_pid(lines, pid):
    want = [0x41, int(pid, 16)]
    for l in lines:
        try: b = hex_bytes(l)
        except ValueError: continue
        for i in range(len(b) - 1):
            if b[i:i + 2] == want: return b[i + 2:]
    raise ElmError("Brak odpowiedzi na PID %s: %s" % (pid, " | ".join(lines) or "(nic)"))


def decode_dtc_pair(a, b):
    return "PCBU"[a >> 6] + "%d%X%02X" % ((a >> 4) & 3, a & 0xF, b)


def parse_mode03(lines):
    codes = []
    for l in lines:
        if "NO DATA" in l.upper(): continue
        try: b = hex_bytes(l)
        except ValueError: continue
        if 0x43 not in b: continue
        b = b[b.index(0x43) + 1:]
        if len(b) % 2: b = b[1:]     # CAN: bajt liczby błędów
        for i in range(0, len(b) - 1, 2):
            if b[i] or b[i + 1]: codes.append(decode_dtc_pair(b[i], b[i + 1]))
    return codes


class Elm327:
    def __init__(self, j): self.j = j; self.ok = False

    def cmd(self, c, timeout=3.0):
        if not c.upper().replace(" ", "").startswith(ALLOWED_PREFIX):
            raise ElmError("Tylko odczyt: komenda %s zablokowana." % c)
        self.j.write((c + "\r").encode("ascii"))
        r = str(self.j.readUntilPrompt(float(timeout)))
        if not r: raise ElmError("ELM327 nie odpowiada (%s)" % c)
        return clean(r)

    def init(self):
        try:
            ver = self.cmd("ATZ", 5.0)
            for c in ("ATE0", "ATL0", "ATS1", "ATH0", "ATSP0"): self.cmd(c)
            self.ok = True
            return "ELM327: %s. Tylko OBD-II, tylko silnik (DME). Inne moduły E39 wymagają kabla K+DCAN." % (" ".join(ver) or "?")
        except (ElmError, OSError) as e:
            self.ok = False
            return "ELM327: %s – %s" % (NO_LINK, e)

    def live_report(self):
        out = ["Dane na żywo – ELM327 (OBD-II, tylko silnik)"]
        for pid, name, unit, f in PIDS:
            if not self.ok: out.append("%-30s %10s %-6s %s" % (name, DASH, unit, NO_LINK)); continue
            try: out.append("%-30s %10.1f %-6s" % (name, f(parse_pid(self.cmd("01" + pid, 5.0), pid)), unit))
            except (ElmError, OSError, IndexError) as e: out.append("%-30s %10s %-6s %s" % (name, DASH, unit, str(e)[:60]))
        try: v = " ".join(self.cmd("ATRV")) if self.ok else DASH
        except (ElmError, OSError): v = DASH
        out.append("%-30s %10s" % ("Napięcie (gniazdo OBD)", v))
        return "\n".join(out)

    def faults_report(self):
        if not self.ok: return "Błędy OBD-II: %s\n%s" % (DASH, NO_LINK)
        try: codes = parse_mode03(self.cmd("03", 8.0))
        except (ElmError, OSError) as e: return "Błędy OBD-II: %s\n%s" % (DASH, e)
        lines = ["Błędy OBD-II (tryb 03, tylko emisyjne): %d" % len(codes)] + ["• " + c for c in codes]
        if not codes: lines.append("Brak zapisanych błędów OBD-II.")
        lines.append("Uwaga: pełna pamięć błędów BMW (kody ME7.2) tylko przez kabel K+DCAN.")
        return "\n".join(lines)
