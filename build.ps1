# Build script for LightGuard (Windows)
# Usage: run from repository root in PowerShell (recommended: open in project venv)

Set-StrictMode -Version Latest

Write-Host "== LightGuard Build Script =="

# Ensure pip and PyInstaller
Write-Host "Installing/ensuring Python requirements..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# Clean previous builds
if (Test-Path "dist") { Remove-Item -Recurse -Force dist }
if (Test-Path "build") { Remove-Item -Recurse -Force build }
if (Test-Path "lightguard.spec") { Remove-Item -Force lightguard.spec }

# Build single-file windowed exe
Write-Host "Running PyInstaller..."
python -m PyInstaller --noconfirm --onefile --windowed --name lightguard main.py

# Copy EXE to Output\dist so Inno script that references Output\dist finds it
$exe = Join-Path -Path (Get-Location) -ChildPath "dist\lightguard.exe"
$targetDir = Join-Path -Path (Get-Location) -ChildPath "Output\dist"
if (-not (Test-Path $targetDir)) { New-Item -ItemType Directory -Path $targetDir | Out-Null }
if (Test-Path $exe) {
    Copy-Item -Force $exe $targetDir
    Write-Host "Copied $exe -> $targetDir"
} else {
    Write-Host "ERROR: Built exe not found at $exe"
}

# Attempt to run Inno Setup Compiler (ISCC.exe) if installed
$innoPaths = @("$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")
$iss = Join-Path -Path (Get-Location) -ChildPath "Output\LightGuard.InnoSetupScript.iss"
$found = $null
foreach ($p in $innoPaths) {
    if (Test-Path $p) { $found = $p; break }
}
if ($found -ne $null) {
    Write-Host "Found Inno Setup at: $found"
    & $found $iss
    Write-Host "Inno Setup invoked with $iss"
} else {
    Write-Host "Inno Setup Compiler (ISCC.exe) not found. Install Inno Setup and run: ISCC.exe $iss"
}

Write-Host "Build script finished. Check Output folder for installer if Inno ran."
