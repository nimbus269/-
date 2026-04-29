@echo off
setlocal

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo Stopping process %%a on port 8000...
  taskkill /PID %%a /F >nul 2>nul
)

echo Done.
endlocal
