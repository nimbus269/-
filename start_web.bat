@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Detecting Python...
set "PYTHON_CMD="

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
  ) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
      set "PYTHON_CMD=python"
    )
  )
)

if "%PYTHON_CMD%"=="" (
  echo Python not found. Please install Python 3.11+ first.
  pause
  exit /b 1
)

echo [2/4] Checking dependencies...
%PYTHON_CMD% -m pip show fastapi >nul 2>nul
if not %errorlevel%==0 (
  echo Installing requirements...
  %PYTHON_CMD% -m pip install -r requirements.txt
)

set "PORT=8000"
call :pick_port

echo [3/4] Opening browser...
start "" "http://127.0.0.1:%PORT%"

echo [4/4] Starting web server on 0.0.0.0:%PORT% ...
echo.
echo 本机访问: http://127.0.0.1:%PORT%
echo 其他电脑请用本机局域网 IP 访问，例如: http://192.168.x.x:%PORT%
echo 如无法访问，请检查 Windows 防火墙是否放行 %PORT% 端口。
%PYTHON_CMD% -m uvicorn web_app.main:app --host 0.0.0.0 --port %PORT% --reload

endlocal
exit /b 0

:pick_port
for %%p in (8000 8010 8020 8080) do (
  netstat -ano | findstr ":%%p" | findstr "LISTENING" >nul
  if errorlevel 1 (
    set "PORT=%%p"
    goto :eof
  )
)
set "PORT=8090"
goto :eof
