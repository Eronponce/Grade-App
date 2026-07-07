@echo off
cd /d "%~dp0"
echo Grade Lab - iniciando servidor...

REM Mata qualquer processo antigo na porta 8765
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }" >nul 2>&1

start "" http://127.0.0.1:8765/
python -m uvicorn server:app --host 127.0.0.1 --port 8765
pause
