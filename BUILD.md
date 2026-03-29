LightGuard build and installer instructions

1) Requirements
- Python 3.8+ (same interpreter used for run/time)
- Inno Setup 6 (optional, for building installer)
- Optional: a virtual environment

2) Quick build (PowerShell)

Open PowerShell in repository root and run:

```powershell
.\build.ps1
```

This script automates the common steps. If you prefer to run commands manually, the precise steps are below.

3) Manual commands (explicit)

Create and activate a virtual environment (optional but recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install requirements and PyInstaller:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

Build a windowed single-file executable (no console):

```powershell
pyinstaller --onefile --windowed --name lightguard main.py
```

Or build a single-file console executable (shows console output):

```powershell
pyinstaller --onefile --console --name lightguard main.py
```

After PyInstaller completes, copy the result to the installer input folder:

```powershell
mkdir -Force Output\dist
copy .\dist\lightguard.exe .\Output\dist\lightguard.exe
```

Compile the Inno Setup script (command-line):

If `ISCC.exe` is in PATH (Inno Setup installed), run:

```powershell
ISCC.exe Output\LightGuard.InnoSetupScript.iss
```

If Inno is installed in the default location, full path example:

```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" Output\LightGuard.InnoSetupScript.iss
```

4) Optional: Sign the EXE and installer (recommended to avoid SmartScreen warnings)

Use `signtool.exe` from Windows SDK. Example:

```powershell
signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 /v .\Output\dist\lightguard.exe
signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 /v .\Output\LightGuardSetup.exe
```

Adjust the signer options (`/a`, certificate selection, timestamp server) to match your certificate setup.

Notes
- The Inno script `Output\LightGuard.InnoSetupScript.iss` references `Output\dist\lightguard.exe` as the input. Update the `.iss` if you change filenames or add files.
- If you want the installer to include extra resources (icons, license), add them to the `.iss` script before compiling.
- The provided `build.ps1` and `build.bat` automate most of these steps; use them if available.
