# Compila PanelRouter.exe en 64 bits con el Python de 64 bits instalado en la PC.
# Uso:  powershell -NoProfile -ExecutionPolicy Bypass -File compilar-32bits.ps1
# No instala nada en el sistema: Python de 32 bits queda en herramientas\python32.
$ErrorActionPreference = "Stop"
# Si conviven PowerShell 7 y Windows PowerShell, la ruta de módulos heredada rompe
# la carga de módulos (Get-AuthenticodeSignature). Se usa la del sistema.
$env:PSModulePath = [Environment]::GetEnvironmentVariable("PSModulePath", "Machine")

$H      = Split-Path -Parent $MyInvocation.MyCommand.Path
$APP    = Join-Path (Split-Path -Parent $H) "app"
$PY32   = Join-Path $H "python32"
$NUPKG  = Join-Path $H "pythonx86.3.12.10.nupkg"
$URL    = "https://api.nuget.org/v3-flatcontainer/pythonx86/3.12.10/pythonx86.3.12.10.nupkg"

function Paso($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }

# 1) Python de 64 bits del sistema
$PYEXE = (Get-Command python.exe).Source
$bits = & $PYEXE -c "import struct; print(struct.calcsize('P')*8)"
if ($bits.Trim() -ne "64") { throw "El python.exe del sistema no es de 64 bits ($bits)" }
Write-Host "   OK: Python de 64 bits ($PYEXE)"

# 3) PyInstaller en ese Python 
Paso "Instalando PyInstaller en el Python de 64 bits"
# pip y PyInstaller escriben avisos en stderr: en PowerShell 5.1 con "Stop" eso
# sería un error fatal, así que para los programas externos se mira $LASTEXITCODE.
$ErrorActionPreference = "Continue"
& $PYEXE -m pip install --disable-pip-version-check --no-warn-script-location -q "pyinstaller>=6.22" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de PyInstaller" }

# 4) Compilar
Paso "Compilando PanelRouter.exe (64 bits)"
Push-Location $APP
try {
    & $PYEXE -m PyInstaller --noconfirm --onefile --noconsole --name PanelRouter `
        --icon "$APP\recursos\logo.ico" --add-data "$APP\recursos\logo.ico;recursos" `
        --add-data "$APP\web;web" --distpath "$APP\dist64" --workpath "$APP\build64\tmp" `
        --specpath "$APP\build64" servidor.py 2>&1 | Select-Object -Last 2
    if ($LASTEXITCODE -ne 0) { throw "Falló la compilación" }
} finally { Pop-Location }
Remove-Item -Recurse -Force "$APP\build64" -ErrorAction SilentlyContinue

# 5) Confirmar que el .exe es de 32 bits (cabecera PE: 0x014c = x86)
$exe = "$APP\dist64\PanelRouter.exe"
$b = [System.IO.File]::ReadAllBytes($exe)
$pe = [BitConverter]::ToInt32($b, 0x3C)
$maquina = [BitConverter]::ToUInt16($b, $pe + 4)
if ($maquina -ne 0x8664) { throw ("El exe no es de 64 bits (maquina 0x{0:X})" -f $maquina) }
Paso ("LISTO: $exe  ({0:N1} MB, 64 bits - solo Windows de 64 bits)" -f ((Get-Item $exe).Length / 1MB))
