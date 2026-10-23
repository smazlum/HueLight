@echo off
rem HueLight sunucusunu baslatir. Ilk calistirmada Python ortamini kurar.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Python ortami kuruluyor...
    python -m venv .venv || goto :error
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :error
)
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul && (
    echo HueLight zaten calisiyor.
    start "" http://localhost:8000
    goto :eof
)
start "" http://localhost:8000
".venv\Scripts\python.exe" -m backend.main --port 8000
goto :eof

:error
echo Kurulum basarisiz. Python 3.10+ kurulu mu?
pause
