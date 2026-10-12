"""Dostęp TYLKO DO ODCZYTU do pozostałych modułów E39 przez DS2 (K-line): identyfikacja (00) i pamięć błędów (04).
Kodowanie (NCS), flash (WinKFP) i EWS celowo WYŁĄCZONE – ten moduł odrzuca każdą komendę spoza białej listy.
Adresy z ds2.MODULES; żaden nie jest jeszcze potwierdzony na TYM aucie (wymaga testu na samochodzie).
Bajty odpowiedzi pokazywane surowo – bez SGBD danego modułu nie zgadujemy znaczenia."""
from . import ds2
from .me72 import hexs, DmeError

READ_ONLY_CMDS = {ds2.CMD_IDENT, ds2.CMD_FAULTS}
EWS_ADDR = 0x44         # EWS – zablokowane niezależnie od komendy
NO_LINK = "brak połączenia"


class WriteBlocked(PermissionError):
    pass


class ReadOnlyDs2:
    def __init__(self, ds2_obj): self.d = ds2_obj

    def request(self, addr, data):
        if addr == EWS_ADDR: raise WriteBlocked("EWS jest zablokowany w tej wersji.")
        if not data or data[0] not in READ_ONLY_CMDS or len(data) != 1:
            raise WriteBlocked("Tylko odczyt: komenda %s zablokowana (kodowanie/flash/kasowanie wyłączone)." % hexs(bytes(data or b"")))
        return self.d.request(addr, data)

    def read_module(self, name, addr):
        res = {"moduł": name, "adres": "0x%02X" % addr, "identyfikacja": "—", "błędy (surowo)": "—", "status": "", "zweryfikowane": "NIE – wymaga testu na aucie"}
        errs = []
        for key, cmd in (("identyfikacja", ds2.CMD_IDENT), ("błędy (surowo)", ds2.CMD_FAULTS)):
            try: res[key] = hexs(self.request(addr, [cmd]))
            except (DmeError, OSError) as e: errs.append(str(e).split(".")[0])
        res["status"] = "OK" if not errs else "; ".join(errs)
        return res

    def scan(self):
        return [self.read_module(n, a) for n, a in ds2.MODULES if a != EWS_ADDR]


def offline_table():
    return [{"moduł": n, "adres": "0x%02X" % a, "identyfikacja": "—", "błędy (surowo)": "—", "status": NO_LINK,
             "zweryfikowane": "NIE – wymaga testu na aucie"} for n, a in ds2.MODULES]


def scan_rows(ds2_obj):
    """Skan modułów przez bramkę tylko-do-odczytu; format wierszy jak ds2.Ds2.scan(). EWS pominięty."""
    g = ReadOnlyDs2(ds2_obj); out = []
    for name, a in ds2.MODULES:
        if a == EWS_ADDR: continue
        row = [name, "0x%02X" % a]
        for cmd in (ds2.CMD_IDENT, ds2.CMD_FAULTS):
            try: row.append(hexs(g.request(a, [cmd])))
            except Exception as e: row.append("— " + str(e).split(".")[0])
        out.append(row)
    return out
