@echo off
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt pyinstaller
pyinstaller --noconfirm --onefile --windowed --name AutoDiagPro_real autodiag_real\app.py
echo Gotowe: dist\AutoDiagPro_real.exe
pause
