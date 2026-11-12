# Compila PanelRouter.exe en 32 bits (corre en Windows de 32 Y de 64 bits).
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

# 1) Python 3.12 de 32 bits (paquete oficial de la Python Software Foundation)
if (-not (Test-Path (Join-Path $PY32 "python.exe"))) {
    Paso "Descargando Python 3.12.10 de 32 bits (NuGet oficial)"
    & curl.exe -sSL --fail -o $NUPKG $URL
    if ($LASTEXITCODE -ne 0) { throw "No se pudo descargar $URL" }
    Paso "Descomprimiendo"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($NUPKG)
    try {
        foreach ($e in $zip.Entries) {
            if ($e.FullName -like "tools/*" -and -not $e.FullName.EndsWith("/")) {
                $dest = Join-Path $PY32 ($e.FullName.Substring(6) -replace "/", "\")
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
                [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, $dest, $true)
            }
        }
    } finally { $zip.Dispose() }
}
$PYEXE = Join-Path $PY32 "python.exe"

# 2) Verificaciones: firma y arquitectura
Paso "Verificando firma digital de python.exe"
$firma = Get-AuthenticodeSignature -LiteralPath $PYEXE
if ($firma.Status -ne "Valid" -or $firma.SignerCertificate.Subject -notmatch "Python Software Foundation") {
    throw "Firma NO válida: $($firma.Status) / $($firma.SignerCertificate.Subject)"
}
Write-Host "   OK: $($firma.SignerCertificate.Subject.Split(',')[0])"
$bits = & $PYEXE -c "import struct; print(struct.calcsize('P')*8)"
if ($bits.Trim() -ne "32") { throw "Este Python no es de 32 bits ($bits)" }
Write-Host "   OK: Python de 32 bits"

# 3) PyInstaller en ese Python (no toca el Python de 64 bits de la PC)
Paso "Instalando PyInstaller en el Python de 32 bits"
# pip y PyInstaller escriben avisos en stderr: en PowerShell 5.1 con "Stop" eso
# sería un error fatal, así que para los programas externos se mira $LASTEXITCODE.
$ErrorActionPreference = "Continue"
& $PYEXE -m ensurepip --upgrade 2>&1 | Out-Null
& $PYEXE -m pip install --disable-pip-version-check --no-warn-script-location -q "pyinstaller==6.22.3" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de PyInstaller" }

# 4) Compilar
Paso "Compilando PanelRouter.exe (32 bits)"
Push-Location $APP
try {
    & $PYEXE -m PyInstaller --noconfirm --onefile --noconsole --name PanelRouter `
        --icon "$APP\recursos\logo.ico" --add-data "$APP\recursos\logo.ico;recursos" `
        --add-data "$APP\web;web" --distpath "$APP\dist32" --workpath "$APP\build32\tmp" `
        --specpath "$APP\build32" servidor.py 2>&1 | Select-Object -Last 2
    if ($LASTEXITCODE -ne 0) { throw "Falló la compilación" }
} finally { Pop-Location }
Remove-Item -Recurse -Force "$APP\build32" -ErrorAction SilentlyContinue

# 5) Confirmar que el .exe es de 32 bits (cabecera PE: 0x014c = x86)
$exe = "$APP\dist32\PanelRouter.exe"
$b = [System.IO.File]::ReadAllBytes($exe)
$pe = [BitConverter]::ToInt32($b, 0x3C)
$maquina = [BitConverter]::ToUInt16($b, $pe + 4)
if ($maquina -ne 0x014c) { throw ("El exe no es de 32 bits (maquina 0x{0:X})" -f $maquina) }
Paso ("LISTO: $exe  ({0:N1} MB, 32 bits - funciona en Windows de 32 y 64 bits)" -f ((Get-Item $exe).Length / 1MB))
