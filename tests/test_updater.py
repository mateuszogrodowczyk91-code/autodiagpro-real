"""Testy aktualizatora na danych lokalnych (bez sieci)."""
import hashlib, io, json, os, sys, zipfile, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from autodiag_real import updater


def make_zip():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z: z.writestr(updater.EXE, b"MZ fake"); z.writestr("README_PL.txt", "x")
    return b.getvalue()


def fetcher(zipbytes, sha, tag="v9.9.9", sums=True):
    rel = {"tag_name": tag, "body": "Zmiany", "assets": [{"name": "AutoDiagPro_real-9.9.9.zip", "browser_download_url": "Z"}]}
    if sums: rel["assets"].append({"name": "SHA256SUMS.txt", "browser_download_url": "S"})
    else: rel["body"] += "\nSHA256: " + sha
    data = {updater.API: json.dumps(rel).encode(), "Z": zipbytes, "S": ("%s  AutoDiagPro_real-9.9.9.zip\n" % sha).encode()}
    return lambda url, *a: data[url]


def test_versions():
    assert updater.is_newer("v1.1.1", "1.1.0") and not updater.is_newer("v1.1.0", "1.1.0") and updater.is_newer("1.10.0", "1.9.9")


@pytest.mark.parametrize("sums", [True, False])
def test_check_download_verify(tmp_path, sums):
    z = make_zip(); sha = hashlib.sha256(z).hexdigest(); f = fetcher(z, sha, sums=sums)
    info = updater.check(f); assert info["version"] == "9.9.9" and info["sha256"] == sha
    stage = updater.download_and_stage(info, f, str(tmp_path)); assert os.path.isfile(os.path.join(stage, updater.EXE))


def test_bad_hash_rejected(tmp_path):
    z = make_zip(); f = fetcher(z, "0" * 64)
    with pytest.raises(updater.UpdateError, match="NIE zgadza"): updater.download_and_stage(updater.check(f), f, str(tmp_path))


def test_no_newer():
    assert updater.check(fetcher(make_zip(), "0" * 64, tag="v1.0.0")) is None


def test_no_network_message():
    def f(*a): raise updater.UpdateError("Brak internetu – nie można sprawdzić aktualizacji. Program działa normalnie.")
    with pytest.raises(updater.UpdateError, match="Brak internetu"): updater.check(f)


def test_swap_script_keeps_backup():
    s = updater.swap_script(r"C:\s", 123, r"C:\app", r"C:\bk", "1.1.0")
    assert "Wait-Process -Id 123" in s and "app_1.1.0_" in s and "Start-Process" in s
    assert "flash" not in s.lower()


def test_safe_extract_rejects_zip_slip(tmp_path):
    import io, zipfile, pytest
    from autodiag_real import updater
    for bad in ("../x.txt", "/abs.txt", "C:/win.txt", "a\\..\\..\\x.txt"):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z: z.writestr(bad, "x")
        with zipfile.ZipFile(b) as z:
            with pytest.raises(updater.UpdateError): updater.safe_extract(z, str(tmp_path / "s"))
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z: z.writestr("ok/a.txt", "x")
    with zipfile.ZipFile(b) as z: updater.safe_extract(z, str(tmp_path / "s"))
    assert (tmp_path / "s" / "ok" / "a.txt").exists()
