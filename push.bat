@echo off
title Push Banking System to GitHub
cd /d "%~dp0"
echo ===================================================================
echo     PUSHING SIMPLE BANKING SYSTEM TO GITHUB
echo     Target: https://github.com/Srinivas791/banking-system.git
echo ===================================================================
echo.
git push -u origin main
echo.
if %errorlevel% equ 0 (
    echo [SUCCESS] Code successfully pushed to your repository!
    echo [NEXT STEP] Go to https://dashboard.render.com to deploy it in 1 click.
) else (
    echo [ERROR] Push did not complete. Please check your GitHub permissions or sign-in prompt.
)
pause
