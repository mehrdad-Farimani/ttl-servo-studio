@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -c "import ttl_servo_studio, serial" 2>nul
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install .
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m ttl_servo_studio
if errorlevel 1 goto fail
exit /b 0
:fail
pause
exit /b 1
