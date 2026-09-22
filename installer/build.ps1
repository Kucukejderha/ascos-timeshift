$projectDir = Split-Path -Parent $PSScriptRoot
$wix = "$env:USERPROFILE\.dotnet\tools\wix.exe"

Get-Process -Name TimeShift, TimeShiftGui -ErrorAction SilentlyContinue | Stop-Process -Force

python -m PyInstaller --noconfirm --clean --log-level WARN --onefile --console --name TimeShift `
  --icon "$projectDir\assets\ASCOS-TimeShift.ico" `
  --add-data "$projectDir\agent.js;." --distpath "$projectDir\dist" `
  --workpath "$projectDir\build\cli" --specpath "$projectDir\build\cli" `
  "$projectDir\timeshift.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (CLI) basarisiz, kod: $LASTEXITCODE" }

python -m PyInstaller --noconfirm --clean --log-level WARN --onefile --windowed --name TimeShiftGui `
  --icon "$projectDir\assets\ASCOS-TimeShift.ico" `
  --add-data "$projectDir\agent.js;." `
  --add-data "$projectDir\assets\ASCOS-TimeShift.ico;assets" `
  --add-data "$projectDir\assets\ASCOS-TimeShift-52.png;assets" `
  --add-data "$projectDir\assets\ASCOS-TimeShift-128.png;assets" `
  --distpath "$projectDir\dist" `
  --workpath "$projectDir\build\gui" --specpath "$projectDir\build\gui" `
  "$projectDir\timeshift_gui.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (GUI) basarisiz, kod: $LASTEXITCODE" }

Push-Location $PSScriptRoot
try {
  & $wix build -arch x64 -ext WixToolset.UI.wixext -culture tr-TR `
    -o "$projectDir\ASCOS-TimeShift-1.0.0.msi" "Product.wxs"
  if ($LASTEXITCODE -ne 0) { throw "wix build basarisiz, kod: $LASTEXITCODE" }
} finally {
  Pop-Location
}
