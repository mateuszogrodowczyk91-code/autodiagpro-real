"""Kreator „Nie odpala na zimno” – BMW E39 540i M62TU / Bosch ME7.2. TYLKO ODCZYT.
Używa wyłącznie odczytów: engine() / roughness() (live.py / me72.py) i read_faults() + bmw_dtc.describe().
Nie kasuje błędów, nie flashuje, nie koduje, nie dotyka EWS.
Bez połączenia: wartości "—", status "brak połączenia" i BRAK werdyktu. Żadnych danych przykładowych.

WSZYSTKIE PROGI PONIŻEJ SĄ WSTĘPNE – WYMAGAJĄ WERYFIKACJI NA AUCIE."""
from . import me72, bmw_dtc
from .live import DASH, NO_LINK

VERIFY = "próg wstępny – do weryfikacji na aucie"
# Progi (NIEZWERYFIKOWANE na aucie)
BATT_LOW_V = 12.2          # kluczyk poz. 2, silnik stoi: < 12,2 V = akumulator słaby/rozładowany
BATT_CRIT_V = 11.8
CTS_IAT_MAX_DIFF_C = 15.0  # zimny silnik: |płyn − powietrze| > ~15 °C = czujnik temp. płynu podejrzany
COLD_ENGINE_MAX_C = 40.0   # powyżej tego nie traktujemy silnika jako zimnego (porównanie CTS/IAT bez sensu)
ROUGH_SAMPLES = 10
PLUGS = "Bosch FGR7DQP lub NGK BKR6EQUP (BMW 12 12 0 037 608), komplet 8 szt., 30 Nm na zimnym silniku"

_KW = {"cts": ("kühlmittel", "coolant", "temperaturfühler motor", "ntc"),
       "misfire": ("zünd", "misfire", "verbrennungsaussetzer", "aussetzer", "zuend"),
       "coil": ("zündspule", "zuendspule", "ignition coil", "coil"),
       "pump": ("kraftstoffpumpe", "fuel pump", "elektrokraftstoffpumpe", "ekp"),
       "batt": ("batteriespannung", "bordnetz", "battery", "voltage")}


def _val(rows, name):
    for n, v, *_ in rows:
        if n == name and isinstance(v, (int, float)): return float(v)
    return None


def _classify(text):
    t = text.lower()
    return {k for k, kws in _KW.items() if any(w in t for w in kws)}


def run(dme, samples=ROUGH_SAMPLES):
    """dme: me72.Me72 albo None. Zwraca dict: connected, steps [(krok, wartość, status)], verdict [(punkty, przyczyna, powody)], note."""
    steps, connected = [], False
    if dme is None:
        steps = [(s, DASH, NO_LINK) for s in ("Napięcie akumulatora", "Temp. płynu", "Temp. powietrza", "Różnica płyn–powietrze",
                                               "Nierówność cylindrów", "Błędy ME7.2")]
        return {"connected": False, "steps": steps, "verdict": [], "note": NO_LINK + " – brak werdyktu"}
    score = {}
    def add(key, pts, why): s = score.setdefault(key, [0, []]); s[0] += pts; s[1].append(why)

    # 1+2: akumulator, CTS vs IAT
    try:
        eng = dme.engine(); connected = True
        u, cts, iat = (_val(eng, "Napięcie akumulatora (DME)"), _val(eng, "Temp. płynu chłodzącego"), _val(eng, "Temp. powietrza dolotowego"))
        steps += [("Napięcie akumulatora", u if u is not None else DASH, "V"), ("Temp. płynu", cts if cts is not None else DASH, "°C"),
                  ("Temp. powietrza", iat if iat is not None else DASH, "°C")]
        if u is not None and u < BATT_LOW_V:
            add("batt", 3 if u < BATT_CRIT_V else 2, "Napięcie %.1f V < %.1f V (%s). Naładuj i sprawdź przy kręceniu." % (u, BATT_LOW_V, VERIFY))
        if cts is not None and iat is not None:
            d = cts - iat
            steps.append(("Różnica płyn–powietrze", round(d, 1), "°C"))
            if cts < -39 or cts > 130:
                add("cts", 4, "Temp. płynu %.0f °C jest nierealna – przerwa/zwarcie czujnika lub przewodu." % cts)
            elif min(cts, iat) <= COLD_ENGINE_MAX_C and abs(d) > CTS_IAT_MAX_DIFF_C:
                add("cts", 3, "Zimny silnik: płyn %.0f °C vs powietrze %.0f °C (różnica %.0f > %.0f °C, %s). DME źle dawkuje paliwo na zimno."
                    % (cts, iat, abs(d), CTS_IAT_MAX_DIFF_C, VERIFY))
            elif min(cts, iat) > COLD_ENGINE_MAX_C:
                steps.append(("Uwaga", "silnik nie jest zimny", "porównanie CTS/IAT niemiarodajne"))
    except me72.DmeError as e:
        steps += [("Akumulator / temperatury", DASH, str(e).split(".")[0])]

    # 3: nierówność biegu
    rough = []
    for _ in range(samples):
        try: rough.append(dme.roughness()); connected = True
        except me72.DmeError: break
    if rough:
        _, _, worst, desc = me72.roughness_outlier(rough)
        steps.append(("Nierówność cylindrów", desc, "%d próbek, mapowanie poz.→cyl. z SGBD, do potwierdzenia na aucie" % len(rough)))
        if worst is not None:
            add("coil:%d" % (worst + 1), 2, "%s odstaje w nierówności biegu (cylinder do potwierdzenia na aucie). Zamień cewkę z sąsiednim cylindrem i sprawdź, czy problem idzie za cewką." % me72.rough_label(worst + 1).capitalize())
            add("plugs", 1, "Odstający cylinder – świeca też możliwa.")
    else:
        steps.append(("Nierówność cylindrów", DASH, "brak danych (silnik musi pracować)"))

    # 4: błędy ME7.2
    try:
        _, recs, warn = dme.read_faults(); connected = True
        steps.append(("Błędy ME7.2", len(recs), "; ".join(warn) or "OK"))
        for code, _st in recs:
            txt = bmw_dtc.describe(code); cl = _classify(txt)
            steps.append(("Błąd %d" % code, txt, ""))
            if "cts" in cl: add("cts", 3, "Błąd w pamięci: %s" % txt)
            if "coil" in cl: add("plugs", 1, "Błąd zapłonu: %s" % txt)
            elif "misfire" in cl: add("plugs", 2, "Wypadanie zapłonu: %s" % txt)
            if "pump" in cl: add("pump", 3, "Błąd pompy: %s" % txt)
            if "batt" in cl: add("batt", 1, "Błąd zasilania: %s" % txt)
    except me72.DmeError as e:
        steps.append(("Błędy ME7.2", DASH, str(e).split(".")[0]))

    if not connected:
        return {"connected": False, "steps": [(s, DASH, NO_LINK) for s, *_ in steps], "verdict": [], "note": NO_LINK + " – brak werdyktu"}

    label = {"batt": "Akumulator", "cts": "Czujnik temperatury płynu (CTS)", "plugs": "Świece zapłonowe: " + PLUGS,
             "pump": "Pompa paliwa / przekaźnik pompy"}
    # pompy nie widać w danych na żywo – zawsze jako kontrola ręczna, na końcu jeśli brak dowodów
    add("pump", 0, "Kluczyk poz. 2: spod tylnej kanapy ma być słychać szum pompy 1–2 s. Cisza = pompa lub przekaźnik.")
    verdict = []
    for k, (pts, why) in score.items():
        name = ("Zapłon/cewka – %s, do potwierdzenia na aucie" % me72.rough_label(int(k.split(":")[1]))) if k.startswith("coil:") else label[k]
        verdict.append((pts, name, why))
    verdict.sort(key=lambda v: -v[0])
    return {"connected": True, "steps": steps, "verdict": verdict,
            "note": "Werdykt orientacyjny. Wszystkie progi i mapowania wymagają weryfikacji na aucie."}


def format_report(res):
    lines = ["Kreator: Nie odpala na zimno (E39 540i M62TU, ME7.2) – tylko odczyt"]
    lines += ["  %s: %s %s" % s for s in res["steps"]]
    if not res["verdict"]:
        lines.append("Werdykt: " + DASH + " (" + res["note"] + ")"); return "\n".join(lines)
    lines.append("Werdykt (od najbardziej prawdopodobnej):")
    for i, (pts, name, why) in enumerate(res["verdict"], 1):
        lines.append("%d. %s [%d pkt]" % (i, name, pts)); lines += ["   – " + w for w in why]
    lines.append(res["note"]); return "\n".join(lines)
