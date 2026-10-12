"""Opisy błędów DME ME7.2 – integracja pracy Engineer Bota (AutoDiagPro_poprawiony: app/knowledge/bmw_dtc.py,
definitions/dtc/bmw_me72_prg.json – 131 kodów, tekst niemiecki z tabeli FORTTEXTE12 SGBD me72kwp0/1.prg).

WAŻNE: plik bmw_me72_prg.json jest pochodną danych BMW (oznaczony "nie publikować"), a to repozytorium jest PUBLICZNE.
Dlatego plik NIE jest w repo – aplikacja szuka go lokalnie u użytkownika (kolejność):
  1. zmienna środowiskowa AUTODIAG_PRG_DTC (pełna ścieżka),
  2. <folder aplikacji>/definitions/dtc/bmw_me72_prg.json,
  3. %USERPROFILE%/Desktop/AutoDiagPro_poprawiony/definitions/dtc/bmw_me72_prg.json,
  4. %USERPROFILE%/Projects/_bmw_data/bmw_me72_prg.json.
Brak pliku -> zapasowo publiczna lista me72_dtc.CODES (EN, endtuning.com). Kod spoza obu list -> "NIEZNANY".

Mapowanie 1 bajtu ORT z odpowiedzi DME na numer z listy jest NIEPEWNE – do potwierdzenia na aucie (porównanie z INPA).
.prg nie jest tu ponownie dekodowany."""
import json
import os

from . import me72_dtc

UNCERTAIN = "mapowanie ORT→nr NIEPEWNE, do potwierdzenia na aucie"
_cache = {}


def candidate_paths():
    env = os.environ.get("AUTODIAG_PRG_DTC")
    home = os.path.expanduser("~")
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = [env] if env else []
    out += [os.path.join(base, "definitions", "dtc", "bmw_me72_prg.json"),
            os.path.join(home, "Desktop", "AutoDiagPro_poprawiony", "definitions", "dtc", "bmw_me72_prg.json"),
            os.path.join(home, "Projects", "_bmw_data", "bmw_me72_prg.json")]
    return out


def load_prg(path=None):
    """{numer: wpis} z lokalnego pliku SGBD-JSON; {} gdy brak/uszkodzony. Zwraca też ścieżkę źródła."""
    paths = [path] if path else candidate_paths()
    for p in paths:
        if not p or not os.path.isfile(p): continue
        if p not in _cache:
            try:
                with open(p, encoding="utf-8") as f: codes = json.load(f).get("codes", [])
                _cache[p] = {int(e["decimal"]): e for e in codes
                             if isinstance(e, dict) and "decimal" in e and 0 <= int(e["decimal"]) <= 0xFF}
            except (OSError, ValueError, TypeError, KeyError):
                _cache[p] = {}
        if _cache[p]: return _cache[p], p
    return {}, None


def number(code):
    if isinstance(code, int): return code
    try: return int(str(code).strip(), 16)
    except ValueError: return None


def describe(code, prg_path=None):
    n = number(code)
    if n is None: return "NIEZNANY – nieczytelny kod (%s)" % (code,)
    prg, src = load_prg(prg_path)
    p = prg.get(n); en = me72_dtc.CODES.get(n)
    if p:
        txt = str(p.get("text", "")).strip().rstrip(",")
        return "%sDE: %s [ME7.2 nr %d; źródło: lokalny SGBD %s; %s]" % ((en + " / ") if en else "", txt, n, p.get("source", "?"), UNCERTAIN)
    if en:
        return "%s [ME7.2 nr %d; źródło: publiczna lista DME 7.2; %s]" % (en, n, UNCERTAIN)
    return "NIEZNANY – brak na liście ME7.2 (nr %d)" % n


def source_status():
    prg, src = load_prg()
    return ("Opisy DE z lokalnego SGBD: %s (%d kodów)" % (src, len(prg))) if src else \
        "Brak lokalnego bmw_me72_prg.json – opisy z publicznej listy EN (%d kodów)" % len(me72_dtc.CODES)
