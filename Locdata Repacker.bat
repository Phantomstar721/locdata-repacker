@echo off
setlocal
cd /d "%~dp0"
py -3 run_repacker.py
if errorlevel 1 pause

