@echo off
tasklist | findstr /I "LightGuard.exe" >nul
IF NOT ERRORLEVEL 1 (
    taskkill /F /IM LightGuard.exe
    timeout /t 2 >nul
)
start "" "%USERPROFILE%\AppData\Local\LightGuard\LightGuard.exe"
exit