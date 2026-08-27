@echo off
setlocal
cd /d "%~dp0"
:loop
echo [%date% %time%] Starting bot...>> restart.log
".venv\Scripts\python.exe" bot.py
echo [%date% %time%] Bot exited code %errorlevel% >> restart.log
timeout /t 5 /nobreak >nul
goto loop
