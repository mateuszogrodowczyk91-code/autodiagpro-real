"""Most Android <-> logika AutoDiagPro (Python, ten sam kod co na laptopie: autodiag_real/me72, ds2, live, coldstart, bmw_dtc).
TYLKO ODCZYT. Flash (WinKFP), kodowanie (NCS), EWS i kasowanie błędów są zablokowane w tym pliku (biała lista komend).
Bez połączenia każda funkcja zwraca "—" / "brak połączenia". Żadnych danych przykładowych."""
import os

from autodiag_real import me72, ds2, live, coldstart, bmw_dtc, modules_ro
import elm327

NO_LINK = live.NO_LINK
DASH = live.DASH
DME_READ_SIDS = {0xA2, 0x22, 0x18}   # ident, readDataByLocalIdentifier, readDTCByStatus


class WriteBlocked(PermissionError):
    pass


class JavaLink:
    """Owija obiekt Kotlin (UsbKLink): setTimeout(s), clear(), write(byte[]), read(n) -> byte[]."""
    def __init__(self, j):
        self.j = j; self.name = str(j.getName())

    def set_timeout(self, s): self.j.setTimeout(float(s))
    def clear(self): self.j.clear()
    def write(self, b): self.j.write(bytes(b))
    def read(self, n):
        r = self.j.read(int(n))
        return bytes((x & 0xFF) for x in r) if r is not None else b""
    def close(self): self.j.close()


CLEAR_WARN = ("Kasowanie pamięci błędów DME (14 FF 00). Zapłon WŁĄCZONY (poz. 2), silnik ZGASZONY.\n"
              "UWAGA: komenda NIE jest jeszcze zweryfikowana na aucie (nie znaleziona w me72kwp1.prg).")


class ReadOnlyTransport(me72.Me72Transport):
    """Odczyt + wyłącznie kasowanie błędów (14 FF 00), i to tylko z allow_clear=True po potwierdzeniu w UI."""
    def request(self, payload, allow_clear=False):
        if allow_clear and list(payload) == list(me72.CLEAR_DTC):
            return super().request(payload)
        if not payload or payload[0] not in DME_READ_SIDS:
            raise WriteBlocked("Tylko odczyt: komenda %s zablokowana (kasowanie/flash/kodowanie/EWS wyłączone)." % me72.hexs(bytes(payload or b"")))
        return super().request(payload)


_state = {"mode": None, "dme": None, "ds2": None, "elm": None}


def set_prg_dir(path):
    """Opisy DE (bmw_me72_prg.json) nie są w publicznym repo – użytkownik może skopiować plik do folderu aplikacji."""
    p = os.path.join(str(path), "bmw_me72_prg.json")
    os.environ["AUTODIAG_PRG_DTC"] = p
    return bmw_dtc.source_status()


def attach_kline(jlink):
    link = JavaLink(jlink)
    _state.update(mode="kline", dme=me72.Me72(ReadOnlyTransport(link)), ds2=modules_ro.ReadOnlyDs2(ds2.Ds2(link)), elm=None)
    return "Kabel K+DCAN: port otwarty (%s, 9600 8E1). Połączenie z DME potwierdzi pierwszy odczyt." % link.name


def attach_elm(jlink):
    _state.update(mode="elm", dme=None, ds2=None, elm=elm327.Elm327(jlink))
    return _state["elm"].init()


def detach():
    _state.update(mode=None, dme=None, ds2=None, elm=None)
    return NO_LINK


def _err(e): return str(e).split(".")[0]


def faults():
    if _state["mode"] == "elm": return _state["elm"].faults_report()
    dme = _state["dme"]
    if dme is None: return "Błędy ME7.2: %s\n%s" % (DASH, NO_LINK)
    try:
        count, recs, warn = dme.read_faults()
    except (me72.DmeError, OSError) as e:
        return "Błędy ME7.2: %s\n%s" % (DASH, _err(e))
    lines = ["Błędy ME7.2 (DME 0x12): %d" % count] + ["  " + w for w in warn]
    for code, st in recs:
        lines.append("• %d (0x%02X), status 0x%02X: %s" % (code, code & 0xFFFF, st, bmw_dtc.describe(code)))
    if not recs: lines.append("Brak zapisanych błędów.")
    lines.append(bmw_dtc.source_status())
    return "\n".join(lines)


def live_data():
    if _state["mode"] == "elm": return _state["elm"].live_report()
    rows, _t, ok = live.snapshot(_state["dme"])
    out = ["Dane na żywo ME7.2 – " + live.connection_status(ok)]
    for n, v, u, st in rows:
        vs = ("%.2f" % v) if isinstance(v, float) else str(v)
        out.append("%-30s %10s %-8s %s" % (n, vs, u, "" if st == "OK" else st))
    return "\n".join(out)


def cold_start():
    if _state["mode"] == "elm":
        return "Kreator wymaga kabla K+DCAN (odczyt nierówności cylindrów z ME7.2).\nPrzez ELM327: %s" % DASH
    return coldstart.format_report(coldstart.run(_state["dme"]))


def modules():
    if _state["mode"] == "elm":
        return "Moduły E39 (EGS, ABS, airbag…) są dostępne tylko przez kabel K+DCAN. ELM327 = tylko silnik (OBD-II)."
    d = _state["ds2"]
    rows = d.scan() if d is not None else modules_ro.offline_table()
    out = []
    for r in rows:
        out.append("%s [%s]\n  ident: %s\n  błędy: %s\n  %s | zweryfikowane: %s" %
                   (r["moduł"], r["adres"], r["identyfikacja"], r["błędy (surowo)"], r["status"], r["zweryfikowane"]))
    return "\n".join(out)


def clear_warning():
    return CLEAR_WARN if _state["mode"] != "elm" else elm327.CLEAR_WARN


def clear_faults(confirmed=False):
    """Kasowanie błędów – jedyna odblokowana komenda zapisu. Wymaga confirmed=True (okno potwierdzenia w aplikacji)."""
    if not confirmed: raise WriteBlocked("Kasowanie błędów wymaga potwierdzenia (zapłon wł., silnik zgaszony).")
    if _state["mode"] == "elm": return _state["elm"].clear_faults(confirmed=True)
    dme = _state["dme"]
    if dme is None: return "Kasowanie błędów: %s\n%s" % (DASH, NO_LINK)
    try:
        d = dme.t.request(me72.CLEAR_DTC, allow_clear=True)
    except (me72.DmeError, OSError) as e:
        return "Kasowanie błędów: NIE wykonano – %s" % _err(e)
    if d[:1] != b"\x54": return "Kasowanie błędów: DME nie potwierdziło (odpowiedź %s)" % me72.hexs(d)
    return "Kasowanie błędów: DME potwierdziło (54). Odczytaj błędy ponownie, aby sprawdzić."


def keepalive():
    e = _state["elm"]
    return e.keepalive() if (_state["mode"] == "elm" and e) else DASH


def blocked(feature):
    raise WriteBlocked("%s jest zablokowane w tej wersji (tylko odczyt, dopóki nie sprawdzone na aucie)." % feature)
