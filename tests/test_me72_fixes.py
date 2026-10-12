"""Poprawki Engineer Bota z me72kwp0/1.prg i D_MOTOR.grp."""
import json, os, struct, sys, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from autodiag_real import me72, bmw_dtc, live


def test_rough_mapping_firing_order():
    assert me72.ROUGH_POS_TO_CYL == (1, 5, 8, 4, 6, 3, 7, 2)
    assert sorted(me72.ROUGH_POS_TO_CYL) == list(range(1, 9))
    assert me72.rough_label(2) == "poz. 2 (prawdopodobnie cyl. 5)"
    assert me72.rough_label(8) == "poz. 8 (prawdopodobnie cyl. 2)"


def test_outlier_text_uses_probable_cylinder():
    s = [[0.1] * 2 + [3.0] + [0.1] * 5 for _ in range(6)]
    for x in s:
        for i in range(8): x[i] += i * 0.001
    _, _, w, desc = me72.roughness_outlier(s)
    assert w == 2 and "poz. 3 (prawdopodobnie cyl. 8)" in desc and "potwierdzenia na aucie" in desc


def test_live_roughness_labels():
    src = open(live.__file__, encoding="utf-8").read()
    assert "rough_label" in src and "Nierówność poz. %d" not in src


def test_fra_signed_percent():
    d = bytes([0x62, 0x40, 0x04]) + struct.pack(">hhhh", 0, 0, -32768, 32767)
    rows = me72.decode_adaptations(d)
    assert rows[2][0].endswith("(FRA_W)") and rows[2][2] == "%"
    assert rows[2][1] == pytest.approx(-32768 * 0.0000305)
    assert rows[3][1] == pytest.approx(32767 * 0.0000305)


def test_lambda_min_length_accepts_ews_byte():
    assert len(me72.decode_lambda_status(bytes([0x62, 0x40, 0x07, 0x81]))) == 8
    rows = me72.decode_lambda_status(bytes([0x62, 0x40, 0x07, 0x81, 0x01, 0x00]))
    assert rows[0][1] == "TAK" and rows[7][1] == "TAK"
    with pytest.raises(me72.ProtocolError):
        me72.decode_lambda_status(bytes([0x62, 0x40, 0x07]))


def test_kwp1_only_source(tmp_path):
    codes = [{"decimal": n, "text": "T%d" % n, "source": "me72kwp0.prg/me72kwp1.prg"} for n in (0x01, 0x7A, 0x7F, 0xC9, 0xEC)]
    p = tmp_path / "prg.json"; p.write_text(json.dumps({"codes": codes}), encoding="utf-8")
    m, _ = bmw_dtc.load_prg(str(p))
    for n in (0x7A, 0x7F, 0xC9, 0xEC):
        assert m[n]["source"] == "me72kwp1.prg"
        assert "źródło: lokalny SGBD me72kwp1.prg;" in bmw_dtc.describe(n, str(p))
    assert m[0x01]["source"] == "me72kwp0.prg/me72kwp1.prg"


def test_unverified_markers_kept():
    assert "NIEPOTWIERDZONE" in open(me72.__file__, encoding="utf-8").read().split("READ_DTC", 1)[1][:200]
