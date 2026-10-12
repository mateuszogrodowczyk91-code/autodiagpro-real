"""ELM327 przez Bluetooth – tylko standardowe OBD-II (SAE J1979), tylko silnik. TYLKO ODCZYT (tryby 01 i 03; tryb 04 kasowania zablokowany).
W E39 ELM327 nie widzi pozostałych modułów BMW – do tego potrzebny kabel K+DCAN.
Obiekt Java: write(byte[]), readUntilPrompt(timeout_s) -> str. Bez połączenia: "—" / "brak połączenia"."""
import time

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


CLEAR_WARN = ("Kasowanie błędów OBD-II (tryb 04). Zapłon WŁĄCZONY (poz. 2), silnik ZGASZONY.\n"
              "UWAGA: NIE zweryfikowane na tym aucie. Kasuje też gotowość monitorów emisji.")


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
    def __init__(self, j): self.j = j; self.ok = False; self.rtt = None

    def _raw(self, c, timeout):
        self.j.write((c + "\r").encode("ascii"))
        t0 = time.monotonic()
        r = str(self.j.readUntilPrompt(float(timeout)) or "")
        dt = time.monotonic() - t0
        if r: self.rtt = dt if self.rtt is None else 0.7 * self.rtt + 0.3 * dt
        return r

    def timeout_for(self, base):
        """Adaptacyjny timeout: ~4x średni czas odpowiedzi, min 1 s, max podana wartość bazowa."""
        if self.rtt is None: return base
        return max(1.0, min(base, 4.0 * self.rtt + 0.5))

    def cmd(self, c, timeout=3.0, allow_clear=False, _retry=True):
        if not (allow_clear and c == "04") and not c.upper().replace(" ", "").startswith(ALLOWED_PREFIX):
            raise ElmError("Tylko odczyt: komenda %s zablokowana." % c)
        try:
            r = self._raw(c, self.timeout_for(timeout))
            if not r and self.rtt is not None: r = self._raw(c, timeout)   # druga próba z pełnym czasem
        except OSError as e:
            r = None; err = e
        if not r:
            # zerwane połączenie: ponowne połączenie z backoffem (Kotlin), ponowna inicjalizacja, jedna powtórka
            if _retry and c != "04" and hasattr(self.j, "reconnect") and self.j.reconnect():
                self.init(); return self.cmd(c, timeout, allow_clear, False)
            raise ElmError("ELM327 nie odpowiada (%s)" % c)
        return clean(r)

    def init(self):
        try:
            self.rtt = None
            ver = self.cmd("ATZ", 5.0, _retry=False)
            for c in ("ATE0", "ATL0", "ATS1", "ATH0"): self.cmd(c, _retry=False)
            at2 = self.cmd("ATAT2", _retry=False)          # adaptacyjny timing ELM (agresywny)
            if any("?" in l for l in at2):                  # klon bez AT2: stały timeout 400 ms
                self.cmd("ATAT1", _retry=False); self.cmd("ATST64", _retry=False)
            self.cmd("ATSP0", _retry=False)
            self.ok = True
            return "ELM327: %s. Tylko OBD-II, tylko silnik (DME). Inne moduły E39 wymagają kabla K+DCAN." % (" ".join(ver) or "?")
        except (ElmError, OSError) as e:
            self.ok = False
            return "ELM327: %s – %s" % (NO_LINK, e)

    def keepalive(self):
        """Podtrzymanie połączenia (ATRV – tylko odczyt napięcia). Zwraca napięcie albo '—'."""
        if not self.ok: return DASH
        try: return " ".join(self.cmd("ATRV", 2.0)) or DASH
        except (ElmError, OSError): return DASH

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

    def clear_faults(self, confirmed=False):
        if not confirmed: raise ElmError("Kasowanie wymaga potwierdzenia.")
        if not self.ok: return "Kasowanie błędów OBD-II: %s\n%s" % (DASH, NO_LINK)
        try: r = self.cmd("04", 8.0, allow_clear=True)
        except (ElmError, OSError) as e: return "Kasowanie: NIE wykonano – %s" % e
        ok = any(l.replace(" ", "").startswith("44") for l in r)
        return "Kasowanie błędów OBD-II: %s (%s)" % ("potwierdzone (44)" if ok else "brak potwierdzenia", " | ".join(r) or "(nic)")

    def faults_report(self):
        if not self.ok: return "Błędy OBD-II: %s\n%s" % (DASH, NO_LINK)
        try: codes = parse_mode03(self.cmd("03", 8.0))
        except (ElmError, OSError) as e: return "Błędy OBD-II: %s\n%s" % (DASH, e)
        lines = ["Błędy OBD-II (tryb 03, tylko emisyjne): %d" % len(codes)] + ["• " + c for c in codes]
        if not codes: lines.append("Brak zapisanych błędów OBD-II.")
        lines.append("Uwaga: pełna pamięć błędów BMW (kody ME7.2) tylko przez kabel K+DCAN.")
        return "\n".join(lines)
