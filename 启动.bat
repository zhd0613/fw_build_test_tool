@echo off
title Debug Tool

echo ========================================
echo   Debug Tool - Quick Start
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    echo Download: https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Python found
python --version

:: Check dependencies
echo.
echo [CHECK] Dependencies...
python -c "import paramiko" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies. Check your network.
        pause
        exit /b 1
    )
) else (
    echo [OK] Dependencies ready
)

echo.
echo [START] Launching...
echo.

:: Run
python main.py

echo.
if errorlevel 1 (
    echo [ERROR] Program exited with error. See messages above.
) else (
    echo [DONE] Program exited normally.
)
pause
