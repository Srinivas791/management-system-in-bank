@echo off
title Apex Horizon - Simple Banking Management System
color 0B

echo ===================================================================
echo     APEX HORIZON NATIONAL BANK - SIMPLE BANKING MANAGEMENT SYSTEM
echo            Academic B.Tech Software Engineering Project
echo ===================================================================
echo.

set PYTHON_CMD=python
where python >nul 2>nul
if %errorlevel% neq 0 (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Thonny\python.exe"
)

echo [*] Starting Banking Management Application...
echo [*] Local URL: http://127.0.0.1:5000
echo.
%PYTHON_CMD% app.py

pause
