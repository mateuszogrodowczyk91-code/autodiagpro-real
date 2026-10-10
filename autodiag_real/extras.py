"""Funkcje dodatkowe 1.3 – wszystko liczone z PRAWDZIWYCH odpowiedzi DME / modułów DS2 albo z danych wpisanych przez użytkownika.
Brak przykładowych danych. Każda funkcja dostaje bajty lub wyniki odczytów i tylko je przetwarza."""
import csv, datetime, html, os
from .me72 import hexs, ProtocolError

# ---------------------------------------------------------------- szczegóły błędu (freeze frame)
def freeze_frame_cmd(code):
    """ISO 14230 readStatusOfDTC (17 HH LL) – ME7.2 zwraca status i warunki otoczenia zapisane przy błędzie.
    Format odpowiedzi NIEPOTWIERDZONY na tym aucie – pokazujemy surowe bajty + to, co pewne (kod, status)."""
    return [0x17, (code >> 8) & 0xFF, code & 0xFF]


def decode_freeze_frame(d, code):
    if d[:1] != b"\x57": raise ProtocolError("Nieoczekiwana odpowiedź szczegółów błędu: %s" % hexs(d))
    rows = [("Kod BMW (hex)", "%04X" % code), ("Odpowiedź DME (surowe bajty)", hexs(d))]
    if len(d) >= 5:
        st = d[4]
        rows += [("Status (hex)", "%02X" % st), ("Status (bity)", format(st, "08b")),
                 ("Błąd obecny teraz (bit 6/7 – wg ISO 14230, niepotwierdzone)", "TAK" if st & 0x40 else "NIE")]
    if len(d) > 5: rows.append(("Warunki otoczenia (surowe, znaczenie wg SGBD – sprawdź w INPA)", hexs(d[5:])))
    return rows


# ---------------------------------------------------------------- dziennik danych na żywo (CSV)
class CsvLogger:
    def __init__(self, path):
        self.path = path; self.f = open(path, "w", newline="", encoding="utf-8-sig"); self.w = csv.writer(self.f, delimiter=";"); self.cols = None; self.rows = 0

    def add(self, live_rows):
        """live_rows = [(nazwa, wartość, jednostka), ...] prosto z Me72.engine()."""
        if self.cols is None:
            self.cols = [n for n, _, _ in live_rows]
            self.w.writerow(["Czas"] + ["%s [%s]" % (n, u) for n, _, u in live_rows])
        vals = {n: x for n, x, _ in live_rows}
        self.w.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]] + [("%.3f" % vals[c]).replace(".", ",") if c in vals else "" for c in self.cols])
        self.rows += 1; self.f.flush()

    def close(self):
        try: self.f.close()
        except Exception: pass


def export_table_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(headers)
        for r in rows: w.writerow([("%.3f" % v).replace(".", ",") if isinstance(v, float) else v for v in r])


# ---------------------------------------------------------------- DS2: czytelna identyfikacja
def ds2_ident_text(raw):
    """Identyfikacja DS2 zwykle zaczyna się od numeru części (ASCII). Pokazujemy znaki drukowalne – reszta zostaje w hex."""
    if not raw: return "—"
    txt = "".join(chr(b) if 32 <= b < 127 else "·" for b in raw)
    return txt.strip("· ") or "—"


# ---------------------------------------------------------------- VIN (dekodowanie numeru wpisanego przez użytkownika)
_YEARS = dict(zip("VWXY123456789ABCDEFGHJKLMNPRST", list(range(1997, 2001)) + list(range(2001, 2010)) + list(range(2010, 2031))))
_TR = {**{str(i): i for i in range(10)}, **dict(zip("ABCDEFGH", range(1, 9))), **dict(zip("JKLMN", range(1, 6))), "P": 7, "R": 9, **dict(zip("STUVWXYZ", range(2, 10)))}
_W = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
WMI = {"WBA": "BMW AG (osobowe)", "WBS": "BMW M GmbH", "WBX": "BMW (SUV)", "4US": "BMW USA", "5UX": "BMW USA (SUV)"}


def decode_vin(vin):
    v = (vin or "").strip().upper().replace(" ", "")
    if len(v) == 7: return [("VIN (końcówka 7 znaków)", v), ("Uwaga", "BMW zapisuje w modułach tylko 7 ostatnich znaków – pełne dekodowanie wymaga 17.")]
    if len(v) != 17 or any(c in "IOQ" for c in v) or not v.isalnum(): raise ValueError("VIN musi mieć 17 znaków (bez I, O, Q) albo 7 ostatnich znaków.")
    s = sum(_TR[c] * w for c, w in zip(v, _W)) % 11; chk = "X" if s == 10 else str(s)
    return [("VIN", v), ("Producent (WMI)", WMI.get(v[:3], v[:3] + " – nieznany kod")), ("Kod typu (VDS)", v[3:9]),
            ("Rok modelowy (10. znak)", str(_YEARS.get(v[9], "?"))), ("Zakład (11. znak)", v[10]), ("Numer seryjny", v[11:]),
            ("Suma kontrolna (9. znak)", "zgodna" if v[8] == chk else "niezgodna (%s, oczekiwano %s – w Europie często nieużywana)" % (v[8], chk))]


# ---------------------------------------------------------------- raport HTML z prawdziwych odczytów
def report_html(sections):
    """sections = [(tytuł, nagłówki, wiersze)] – wyłącznie dane odczytane w tej sesji."""
    out = ["<html><head><meta charset='utf-8'><title>AutoDiag Pro – raport</title><style>body{font-family:Segoe UI,Arial;background:#0b1020;color:#e8ecff}"
           "table{border-collapse:collapse;margin:6px 0 18px 0}td,th{border:1px solid #2a3a5c;padding:4px 8px}th{background:#13224a}</style></head><body>",
           "<h1>AutoDiag Pro – raport diagnostyczny</h1><p>BMW E39 540i · DME ME7.2 · %s</p>" % datetime.datetime.now().strftime("%d.%m.%Y %H:%M")]
    for title, headers, rows in sections:
        out.append("<h2>%s</h2>" % html.escape(title))
        if not rows: out.append("<p><i>nie odczytano w tej sesji</i></p>"); continue
        out.append("<table><tr>%s</tr>" % "".join("<th>%s</th>" % html.escape(str(h)) for h in headers))
        for r in rows: out.append("<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape(("%.2f" % c) if isinstance(c, float) else str(c)) for c in r))
        out.append("</table>")
    out.append("<p style='color:#8d9ab3'>Wszystkie wartości pochodzą z odpowiedzi sterowników w tej sesji.</p></body></html>")
    return "\n".join(out)
