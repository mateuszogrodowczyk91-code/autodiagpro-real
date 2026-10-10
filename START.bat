@echo off
cd /d %~dp0
if not exist .venv (
  echo Tworze srodowisko .venv...
  python -m venv .venv || (echo Brak Pythona 3.10+ w PATH & pause & exit /b 1)
)
call .venv\Scripts\activate
pip install -q -r requirements.txt || (pause & exit /b 1)
python -m autodiag_real.app
if errorlevel 1 pause
