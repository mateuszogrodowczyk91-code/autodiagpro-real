from autodiag_real import coldstart, me72


def eng_bytes(cts_c, iat_c, volt):
    d = bytearray(29); d[0:3] = b"\x62\x40\x00"
    d[18] = int(round((cts_c + 48) / 0.75)); d[17] = int(round((iat_c + 48) / 0.75)); d[25] = int(round(volt / 0.095))
    return bytes(d)


def rough_bytes(vals):
    d = bytearray(19); d[0:3] = b"\x62\x40\x03"
    for i, v in enumerate(vals): d[3 + i * 2:5 + i * 2] = int(v / 0.0027756).to_bytes(2, "big", signed=True)
    return bytes(d)


class D:
    def __init__(self, eng=None, rough=None, faults=None):
        self.e, self.r, self.f = eng, rough, faults
    def engine(self):
        if self.e is None: raise me72.NoResponse("Brak odpowiedzi z DME. x")
        return me72.decode_engine(self.e)
    def roughness(self):
        if self.r is None: raise me72.NoResponse("Brak odpowiedzi z DME. x")
        return me72.decode_roughness(self.r)
    def read_faults(self):
        if self.f is None: raise me72.NoResponse("Brak odpowiedzi z DME. x")
        return me72.decode_dtc(self.f)


def test_offline_no_verdict():
    r = coldstart.run(None)
    assert not r["connected"] and r["verdict"] == [] and all(s[1] == "—" and s[2] == "brak połączenia" for s in r["steps"])
    assert "brak połączenia" in coldstart.format_report(r)


def test_no_response_no_verdict():
    r = coldstart.run(D())
    assert not r["connected"] and r["verdict"] == [] and all(s[1] == "—" for s in r["steps"])


def test_cts_suspect_ranked_first():
    r = coldstart.run(D(eng=eng_bytes(60, 0, 12.6), faults=b"\x58\x00"))
    assert r["verdict"][0][1].startswith("Czujnik temperatury")


def test_cts_ok_when_close():
    r = coldstart.run(D(eng=eng_bytes(2, 0, 12.6), faults=b"\x58\x00"))
    assert all(not v[1].startswith("Czujnik") for v in r["verdict"])


def test_battery_low():
    r = coldstart.run(D(eng=eng_bytes(0, 0, 11.4), faults=b"\x58\x00"))
    assert r["verdict"][0][1] == "Akumulator"


def test_coil_outlier():
    vals = [0.10, 0.12, 0.09, 0.11, 3.0, 0.13, 0.10, 0.12]
    r = coldstart.run(D(eng=eng_bytes(0, 0, 12.6), rough=rough_bytes(vals), faults=b"\x58\x00"))
    names = [v[1] for v in r["verdict"]]
    assert names[0] == "Cewka zapłonowa – cylinder (pozycja) 5" and any("FGR7DQP" in n and "BKR6EQUP" in n for n in names)


def test_pump_check_always_listed_when_connected():
    r = coldstart.run(D(eng=eng_bytes(0, 0, 12.6), faults=b"\x58\x00"))
    assert any("Pompa" in v[1] for v in r["verdict"])
    assert "weryfikacji na aucie" in r["note"]
