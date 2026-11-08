@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Python environment not found. Run setup.bat first.
  pause
  exit /b 1
)

if not exist "models\ss_final_1.pt" (
  echo ERROR: Missing models\ss_final_1.pt
  pause
  exit /b 1
)

".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
