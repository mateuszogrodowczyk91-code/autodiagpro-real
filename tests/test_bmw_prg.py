"""Port testów Engineer Bota (tests/test_bmw_prg.py). Prawdziwy plik SGBD-JSON nie jest w publicznym repo,
więc test właściwy uruchamia się tylko gdy plik jest lokalnie; logikę sprawdzamy na pliku tymczasowym bez tekstów BMW."""
import json, os, pytest
from autodiag_real import bmw_dtc


def _tmp(tmp_path):
    p = tmp_path / "prg.json"
    p.write_text(json.dumps({"codes": [{"code": "0x01", "decimal": 1, "text": "TEST-1,", "source": "test"}]}), encoding="utf-8")
    return str(p)


def test_prg_preferred(tmp_path):
    s = bmw_dtc.describe("0001", prg_path=_tmp(tmp_path))
    assert "DE: TEST-1 " in s and "NIEPEWNE" in s and s.startswith("Leak Diagnosis Pump / ")


def test_fallback_and_unknown(tmp_path):
    p = _tmp(tmp_path)
    assert "publiczna lista" in bmw_dtc.describe("00B6", prg_path=p)
    assert bmw_dtc.describe("2A01", prg_path=p).startswith("NIEZNANY")
    assert bmw_dtc.describe("zz", prg_path=p).startswith("NIEZNANY")


def test_missing_file(tmp_path):
    assert "publiczna lista" in bmw_dtc.describe(1, prg_path=str(tmp_path / "brak.json"))


@pytest.mark.skipif(not bmw_dtc.load_prg()[1], reason="brak lokalnego bmw_me72_prg.json")
def test_real_local_file():
    prg, src = bmw_dtc.load_prg()
    assert len(prg) == 131 and "Leckage" in prg[1]["text"]
