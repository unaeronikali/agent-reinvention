@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%\frontend"

if not exist "node_modules" (
  echo Installing frontend dependencies...
  call npm install
  if errorlevel 1 exit /b 1
)

npm run dev
