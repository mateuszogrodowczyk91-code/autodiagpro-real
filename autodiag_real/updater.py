"""Aktualizacja SAMEGO PROGRAMU z GitHub Releases. Nigdy nie dotyka sterownika auta (żadnego flashowania).

Przebieg: sprawdź najnowsze wydanie -> pobierz ZIP -> sprawdź SHA256 (z pliku SHA256SUMS.txt w wydaniu albo linii
'SHA256: ...' w opisie) -> rozpakuj do katalogu tymczasowego -> po zamknięciu programu mały skrypt PowerShell
przenosi obecną wersję do backups\\ i wstawia nową. Poprzednia wersja zostaje do przywrócenia.
"""
import hashlib, json, os, re, subprocess, sys, tempfile, time, urllib.request, urllib.error, zipfile
from autodiag_real.version import VERSION, REPO

API = "https://api.github.com/repos/%s/releases/latest" % REPO
BASE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AutoDiagPro_real")
APP_DIR = os.path.join(BASE, "app")
BACKUP_DIR = os.path.join(BASE, "backups")
UPD_DIR = os.path.join(BASE, "updates")
EXE = "AutoDiagPro_real.exe"


class UpdateError(Exception):
    pass


def parse_version(v):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in nums[:3]) + (0,) * (3 - len(nums[:3]))


def is_newer(remote, local=VERSION):
    return parse_version(remote) > parse_version(local)


def sha_from_text(text, filename):
    for line in (text or "").splitlines():
        m = re.match(r"\s*([0-9a-fA-F]{64})\s+\*?(\S+)\s*$", line)
        if m and m.group(2) == filename: return m.group(1).lower()
    m = re.search(r"SHA256\s*[:=]\s*`?([0-9a-fA-F]{64})", text or "")
    return m.group(1).lower() if m else None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def _get(url, accept="application/vnd.github+json", timeout=10):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "AutoDiagPro-real/" + VERSION})
    try:
        return urllib.request.urlopen(req, timeout=timeout).read()
    except urllib.error.HTTPError as e:
        if e.code == 404: raise UpdateError("Nie znaleziono wydań programu na GitHub (%s)." % REPO)
        raise UpdateError("Serwer aktualizacji odpowiedział błędem %d." % e.code)
    except (urllib.error.URLError, OSError):
        raise UpdateError("Brak internetu – nie można sprawdzić aktualizacji. Program działa normalnie.")


def check(fetch=_get):
    """Zwraca dict {version, notes, asset_name, asset_url, sha256} albo None gdy brak nowszej wersji."""
    rel = json.loads(fetch(API).decode("utf-8"))
    tag = rel.get("tag_name", "")
    if not is_newer(tag): return None
    assets = rel.get("assets", [])
    z = next((a for a in assets if a["name"].lower().endswith(".zip")), None)
    if not z: raise UpdateError("Wydanie %s nie ma pliku ZIP." % tag)
    sha = None
    sums = next((a for a in assets if a["name"].upper() == "SHA256SUMS.TXT"), None)
    if sums: sha = sha_from_text(fetch(sums["browser_download_url"], "application/octet-stream").decode("utf-8", "replace"), z["name"])
    sha = sha or sha_from_text(rel.get("body", ""), z["name"])
    if not sha: raise UpdateError("Wydanie %s nie podaje sumy SHA256 – aktualizacja przerwana dla bezpieczeństwa." % tag)
    return {"version": tag.lstrip("v"), "notes": rel.get("body", ""), "asset_name": z["name"],
            "asset_url": z["browser_download_url"], "sha256": sha}


def download_and_stage(info, fetch=_get, upd_dir=UPD_DIR):
    os.makedirs(upd_dir, exist_ok=True)
    zpath = os.path.join(upd_dir, info["asset_name"])
    with open(zpath, "wb") as f: f.write(fetch(info["asset_url"], "application/octet-stream", 120))
    got = sha256_file(zpath)
    if got != info["sha256"]:
        os.remove(zpath)
        raise UpdateError("Suma SHA256 pobranego pliku się NIE zgadza (oczekiwano %s, jest %s). Aktualizacja przerwana." % (info["sha256"], got))
    stage = os.path.join(upd_dir, "stage_" + info["version"])
    if os.path.isdir(stage): __import__("shutil").rmtree(stage)
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            if n.startswith("/") or ".." in n.replace("\\", "/").split("/"): raise UpdateError("Niebezpieczna ścieżka w ZIP: " + n)
        z.extractall(stage)
    if not os.path.isfile(os.path.join(stage, EXE)): raise UpdateError("W paczce brak %s." % EXE)
    return stage


def swap_script(stage, pid, app_dir=APP_DIR, backup_dir=BACKUP_DIR, old_version=VERSION):
    """Skrypt PowerShell uruchamiany po zamknięciu programu: backup starej wersji, podmiana, ponowne uruchomienie."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    bk = os.path.join(backup_dir, "app_%s_%s" % (old_version, ts))
    return (
        "$ErrorActionPreference='Stop'\n"
        "try { Wait-Process -Id %d -Timeout 60 -ErrorAction SilentlyContinue } catch {}\n"
        "Start-Sleep -Milliseconds 800\n"
        "New-Item -ItemType Directory -Force -Path '%s' | Out-Null\n"
        "try {\n"
        "  Move-Item -LiteralPath '%s' -Destination '%s'\n"
        "  Move-Item -LiteralPath '%s' -Destination '%s'\n"
        "} catch {\n"
        "  if (-not (Test-Path '%s') -and (Test-Path '%s')) { Move-Item -LiteralPath '%s' -Destination '%s' }\n"
        "  Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Aktualizacja nieudana: ' + $_.Exception.Message + ' Przywrócono poprzednią wersję.') | Out-Null\n"
        "}\n"
        "Start-Process -FilePath '%s'\n"
    ) % (pid, backup_dir, app_dir, bk, stage, app_dir, app_dir, bk, bk, app_dir, os.path.join(app_dir, EXE))


def rollback_script(pid, app_dir=APP_DIR, backup_dir=BACKUP_DIR, cur_version=VERSION):
    ts = time.strftime("%Y%m%d_%H%M%S")
    return (
        "$ErrorActionPreference='Stop'\n"
        "try { Wait-Process -Id %d -Timeout 60 -ErrorAction SilentlyContinue } catch {}\n"
        "Start-Sleep -Milliseconds 800\n"
        "$b = Get-ChildItem -LiteralPath '%s' -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1\n"
        "if ($b) { Move-Item -LiteralPath '%s' -Destination '%s'; Move-Item -LiteralPath $b.FullName -Destination '%s' }\n"
        "Start-Process -FilePath '%s'\n"
    ) % (pid, backup_dir, app_dir, os.path.join(backup_dir, "app_%s_%s_wycofana" % (cur_version, ts)), app_dir, os.path.join(app_dir, EXE))


def has_backup(backup_dir=BACKUP_DIR):
    return os.path.isdir(backup_dir) and any(os.path.isdir(os.path.join(backup_dir, d)) for d in os.listdir(backup_dir))


def can_self_update():
    return getattr(sys, "frozen", False) and os.path.normcase(os.path.dirname(sys.executable)) == os.path.normcase(APP_DIR)


def run_after_exit(script):
    p = os.path.join(tempfile.gettempdir(), "autodiag_update_%d.ps1" % os.getpid())
    with open(p, "w", encoding="utf-8-sig") as f: f.write(script)
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", p],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0))
