$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$SrcPath = Join-Path $Root "src"
$DistPath = Join-Path $Root "dist"
$BuildRoot = Join-Path $Root "build"
$WorkPath = Join-Path $BuildRoot "pyinstaller"
$SpecPath = Join-Path $BuildRoot "pyinstaller_specs"
$EntryPath = Join-Path $BuildRoot "pyinstaller_entrypoints"

Write-Host "Using Python: $Python"

& $Python -c "import PyInstaller" | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "PyInstaller is not installed."
  Write-Host "Install it with: python -m pip install -e .[exe]"
  exit 1
}

New-Item -ItemType Directory -Path $DistPath -Force | Out-Null
New-Item -ItemType Directory -Path $WorkPath -Force | Out-Null
New-Item -ItemType Directory -Path $SpecPath -Force | Out-Null
New-Item -ItemType Directory -Path $EntryPath -Force | Out-Null

$EntryPoints = @(
  @{ Name = "starsector-fontgen"; Module = "starsector_fontgen.cli"; Function = "main" },
  @{ Name = "starsector-fontgen-analyze-fontlib"; Module = "starsector_fontgen.analyze_cli"; Function = "main" },
  @{ Name = "starsector-fontgen-filter-charset"; Module = "starsector_fontgen.filter_cli"; Function = "main" },
  @{ Name = "starsector-fontgen-rebuild-fontlib"; Module = "starsector_fontgen.rebuild_cli"; Function = "main" },
  @{ Name = "starsector-fontgen-build-pack"; Module = "starsector_fontgen.build_pack_cli"; Function = "main" },
  @{ Name = "starsector-fontgen-gui"; Module = "starsector_fontgen.gui"; Function = "main"; Windowed = $true }
)

foreach ($Entry in $EntryPoints) {
  $WrapperPath = Join-Path $EntryPath ($Entry.Name + ".py")
  $Wrapper = @"
from $($Entry.Module) import $($Entry.Function)

if __name__ == "__main__":
    raise SystemExit($($Entry.Function)())
"@
  Set-Content -LiteralPath $WrapperPath -Value $Wrapper -Encoding UTF8

  Write-Host "Building $($Entry.Name).exe"
  $WindowMode = if ($Entry.Windowed) { "--windowed" } else { "--console" }
  & $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    $WindowMode `
    --name $($Entry.Name) `
    --distpath $DistPath `
    --workpath $WorkPath `
    --specpath $SpecPath `
    --paths $SrcPath `
    --exclude-module pytest `
    --exclude-module unittest `
    --exclude-module tests `
    $WrapperPath

  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed while building $($Entry.Name).exe"
  }
}

Write-Host "Done. EXE files are in: $DistPath"
Get-ChildItem -LiteralPath $DistPath -Filter "*.exe" | ForEach-Object {
  Write-Host (" - " + $_.FullName)
}
