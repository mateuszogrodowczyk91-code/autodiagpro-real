import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from autodiag_real import extras, me72


def test_freeze_frame_cmd_and_decode():
    assert extras.freeze_frame_cmd(0x2A11) == [0x17, 0x2A, 0x11]
    rows = dict(extras.decode_freeze_frame(bytes([0x57, 1, 0x2A, 0x11, 0x60, 9, 8]), 0x2A11))
    assert rows["Status (hex)"] == "60" and "09 08" in rows["Warunki otoczenia (surowe, znaczenie wg SGBD – sprawdź w INPA)"]
    with pytest.raises(me72.ProtocolError): extras.decode_freeze_frame(b"\x7f", 1)


def test_csv_logger(tmp_path):
    p = tmp_path / "a.csv"; l = extras.CsvLogger(str(p)); l.add([("Obroty", 750.0, "obr/min")]); l.close()
    txt = p.read_text(encoding="utf-8-sig"); assert "Obroty [obr/min]" in txt and "750,000" in txt


def test_vin():
    d = dict(extras.decode_vin("WBADN6102YGA12345")); assert d["Producent (WMI)"].startswith("BMW") and d["Rok modelowy (10. znak)"] == "2000"
    with pytest.raises(ValueError): extras.decode_vin("abc")


def test_ds2_text(): assert extras.ds2_ident_text(b"\x007545105\x01") == "7545105"


def test_report_only_given_data():
    h = extras.report_html([("X", ["a"], [])]); assert "nie odczytano" in h
