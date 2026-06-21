@echo off
REM Mo giao dien NTH Bot
cd /d "%~dp0"
python run.py
if errorlevel 1 pause
