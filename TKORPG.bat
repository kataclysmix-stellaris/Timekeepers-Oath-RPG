@echo off
cd /d "%~dp0"
py -3 game.py
if errorlevel 1 python game.py
pause
