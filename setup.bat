@echo off
setlocal
cd /d "%~dp0"

if not exist "models\ss_final_1.pt" (
  echo ERROR: Missing models\ss_final_1.pt
  echo Copy the trained model into the models folder before setup.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    where python >nul 2>nul
    if errorlevel 1 (
      echo ERROR: Install Python 3 and add py or python to PATH.
      pause
      exit /b 1
    )
    python -m venv .venv
  )
  if errorlevel 1 goto failed
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo Setup completed. Run run.bat to start SAFESIGHT.
exit /b 0

:failed
echo ERROR: Setup failed. Check the Python installation and network connection.
pause
exit /b 1
