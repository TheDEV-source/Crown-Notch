@echo off
rem Crown Notch launcher — prefers the project virtualenv if it exists.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    py -3.11 main.py 2>nul || python main.py
)
