@echo off
rem ============================================================
rem Antigravity Auto - Fast Runner Script for Windows
rem ============================================================

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXEC=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXEC=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXEC=python"
)

"%PYTHON_EXEC%" main.py %*
