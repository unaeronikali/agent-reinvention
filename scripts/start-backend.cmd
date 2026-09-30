@echo off
setlocal
set "ROOT=%~dp0.."
set "VENV=%ROOT%\.venv"

if not exist "%VENV%\Scripts\activate.bat" (
  echo ERROR: Python virtual environment not found at "%VENV%"
  echo Create it with: py -m venv .venv
  exit /b 1
)

call "%VENV%\Scripts\activate.bat"
cd /d "%ROOT%"

if not exist ".env" (
  echo ERROR: .env not found at "%ROOT%\.env"
  echo Copy .env.example to .env and fill in the required values.
  exit /b 1
)

cd /d "%ROOT%\backend"
echo Backend running with:
where python
python -m uvicorn main:app --reload --port 8000
