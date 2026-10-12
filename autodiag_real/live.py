"""Odczyt parametrów ME7.2 na żywo – jedna migawka wszystkich grup (tylko ODCZYT, usługa 22 = readDataByLocalIdentifier).
Grupy i pozycje bajtów: me72.py (tabela SGBD ME72KWP1, NIE ZWERYFIKOWANE na tym aucie).
Bez połączenia albo przy błędzie grupy: wartość "—" i status "brak połączenia"/opis błędu. Żadnych wartości przykładowych."""
import time

from . import me72

NO_LINK = "brak połączenia"
DASH = "—"
GROUPS = [("silnik", "engine", ["Obroty", "Temp. płynu chłodzącego", "Temp. powietrza dolotowego", "Prędkość", "Czas wtrysku",
                                 "Kąt wyprzedzenia zapłonu", "Przepustnica", "Masa powietrza (MAF)", "Moment wskazany",
                                 "Napięcie akumulatora (DME)"]),
          ("nierówność biegu", "roughness", ["Nierówność poz. %d" % i for i in range(1, 9)]),
          ("lambda", "lambda_status", None)]


def _empty(names, status):
    return [(n, DASH, "", status) for n in (names or [])]


def snapshot(dme):
    """dme: me72.Me72 albo None. Zwraca (wiersze [(nazwa, wartość, jednostka, status)], czas, czy_połączono)."""
    rows, ok_any = [], False
    for label, meth, names in GROUPS:
        if dme is None:
            rows += _empty(names, NO_LINK) or [(label, DASH, "", NO_LINK)]; continue
        try:
            r = getattr(dme, meth)()
            ok_any = True
            if meth == "roughness":
                rows += [("Nierówność poz. %d" % (i + 1), round(v, 3), "1/s", "OK (kolejność cyl. niepotwierdzona)") for i, v in enumerate(r)]
            else:
                rows += [(n, v, u, "OK") for n, v, u in r]
        except me72.DmeError as e:
            msg = str(e).split(".")[0]
            rows += _empty(names, msg) or [(label, DASH, "", msg)]
    return rows, time.time(), ok_any


def connection_status(connected):
    return "połączono z DME" if connected else NO_LINK
