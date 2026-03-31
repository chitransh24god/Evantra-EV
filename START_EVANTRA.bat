@echo off
title Evantra – Starting...
color 0A

echo.
echo  =========================================
echo    EVANTRA EV Charging Platform
echo    Starting backend server...
echo  =========================================
echo.

:: Add PostgreSQL to path
set PATH=%PATH%;C:\Program Files\PostgreSQL\18\bin

:: Go to project folder
cd /d C:\Users\abc\Downloads\evantra

:: Start Flask backend
echo  [1/2] Starting Flask backend on port 5000...
start "Evantra Backend" cmd /k "cd /d C:\Users\abc\Downloads\evantra && python app.py"

:: Wait 3 seconds for backend to start
timeout /t 3 /nobreak >nul

:: Open dashboard in browser
echo  [2/2] Opening Evantra dashboard in browser...
start "" "C:\Users\abc\Downloads\evantra\dashboard.html"

echo.
echo  =========================================
echo    Evantra is running!
echo    Backend: http://127.0.0.1:5000
echo    Close the backend window to stop.
echo  =========================================
echo.
pause
