@echo off
REM Build wrapper for Windows (cmd)
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install pyinstaller
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /f /q lightguard.spec 2>nul
pyinstaller --noconfirm --onefile --windowed --name lightguard main.py
if not exist Output\dist mkdir Output\dist
copy /Y dist\lightguard.exe Output\dist\lightguard.exe
REM Attempt to run Inno Setup if ISCC in PATH
where ISCC.exe >nul 2>&1
if %errorlevel%==0 (
  ISCC.exe Output\LightGuard.InnoSetupScript.iss
) else (
  echo ISCC.exe not found in PATH. Install Inno Setup and run:
  echo ISCC.exe Output\LightGuard.InnoSetupScript.iss
)
echo Build finished.
pause
