param(
    [string]$Version = "1.0.0",
    [string]$PythonExe = "C:\Users\Aswal Ikraam\.gemini\antigravity\scratch\ocean-engineering-toolkit\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PyInstaller = Join-Path (Split-Path -Parent $PythonExe) "pyinstaller.exe"
$DistDir = Join-Path $Root "dist"
$WorkDir = Join-Path $Root "build_tmp"
$ReleaseDir = Join-Path $Root "release"

New-Item -ItemType Directory -Path $DistDir, $ReleaseDir -Force | Out-Null

Write-Host "[1/4] Running smoke tests..."
& $PythonExe (Join-Path $Root "test\smoke_test.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/4] Building single-file EXE with PyInstaller..."
& $PyInstaller --noconfirm --clean --onefile --windowed --name "Ocean PNG Converter" `
  --icon (Join-Path $Root "assets\ocean_png.ico") `
  --add-data ((Join-Path $Root "assets\ocean_png.ico") + ";assets") `
  --add-data ((Join-Path $Root "bj_png_ui") + ";bj_png_ui") `
  --collect-all pypdfium2 --collect-all pypdfium2_raw `
  --exclude-module pymupdf --exclude-module fitz `
  --distpath $DistDir --workpath $WorkDir --specpath $WorkDir `
  (Join-Path $Root "bj_png_app.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/4] Packaging Portable ZIP..."
$ExePath = Join-Path $DistDir "Ocean PNG Converter.exe"
$PortableZip = Join-Path $ReleaseDir "Ocean-PNG-Converter-v$Version-win-x64-Portable.zip"
if (Test-Path $PortableZip) { Remove-Item $PortableZip -Force }
Compress-Archive -Path $ExePath -DestinationPath $PortableZip -CompressionLevel Optimal

Write-Host "[4/4] Building Setup Installer with Inno Setup 6..."
$Iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $Iscc) {
    & $Iscc (Join-Path $Root "installer\OceanPngSetup.iss")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Warning "Inno Setup 6 not found at $Iscc; skipping Setup EXE."
}

Remove-Item $WorkDir -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $ReleaseDir | Select-Object Name, @{N="SizeMB";E={[math]::Round($_.Length/1MB,2)}}
