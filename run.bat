@echo off
setlocal
cd /d "%~dp0"

set "SAFESIGHT_PYTHON=.venv\Scripts\python.exe"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" -c "import torch, flask, cv2, mss, ultralytics, requests; raise SystemExit(0 if torch.cuda.is_available() else 1)" >nul 2>nul
  if not errorlevel 1 set "SAFESIGHT_PYTHON=venv\Scripts\python.exe"
)

if not exist "%SAFESIGHT_PYTHON%" (
  echo ERROR: Python environment not found. Run setup.bat first.
  pause
  exit /b 1
)

if not exist "models\ss_final_2.pt" (
  echo ERROR: Missing models\ss_final_2.pt
  pause
  exit /b 1
)

echo Using %SAFESIGHT_PYTHON%
"%SAFESIGHT_PYTHON%" app.py
if errorlevel 1 pause
