# Optional: build the offline CPP<->Python protocol cross-check harness.
# Requires the pinned core to be built first (scripts/bootstrap-native.ps1).
[CmdletBinding()]
param(
  [string]$Toolset = 'v142'
)
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Core = Join-Path $RepoRoot 'external\ATK-Logic-Mcp\build\Release\atkdl16_core.lib'
if (-not (Test-Path $Core)) {
  throw "Pinned core not built. Run scripts/bootstrap-native.ps1 first ($Core missing)."
}
$Src = Join-Path $RepoRoot 'tests\native'
$Build = Join-Path $Src 'build'

if ($Toolset -eq 'auto') { $Toolset = '' }
if ($Toolset) {
  $prefix = switch -Regex ($Toolset) {
    '^v142$' { '14.2' } '^v143$' { '14.3' } '^v141$' { '14.1' } '^v140$' { '14.0' } default { '' }
  }
  $Vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
  $MsvcRoot = ''
  if (Test-Path $Vswhere) {
    $VsPath = (& $Vswhere -latest -property installationPath 2>$null | Select-Object -First 1)
    if ($VsPath) { $MsvcRoot = Join-Path $VsPath 'VC\Tools\MSVC' }
  }
  if (-not $prefix -or -not $MsvcRoot -or -not (Get-ChildItem $MsvcRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "$prefix*" })) {
    Write-Warning "Toolset '$Toolset' is not installed locally; falling back to the machine default toolset."
    $Toolset = ''
  }
}

$args = @('-S', $Src, '-B', $Build, '-G', 'Visual Studio 17 2022', '-A', 'x64')
if ($Toolset) { $args += @('-T', $Toolset) }
& cmake @args
if ($LASTEXITCODE -ne 0) { throw 'Harness CMake configure failed' }
cmake --build $Build --config Release --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Harness build failed' }

$Dll = Join-Path $RepoRoot 'external\ATK-Logic-Mcp\third_party\libusb\VS2022\MS64\dll\libusb-1.0.dll'
if (Test-Path $Dll) { Copy-Item -LiteralPath $Dll -Destination (Join-Path $Build 'Release') -Force }
Write-Host "[OK] Tools at $(Join-Path $Build 'Release'): dl16-vector-dump.exe (offline cross-check), dl16-pwm.exe (bounded PWM sender)"
Write-Host 'Run pytest; tests/test_protocol_vectors.py will pick up the vector harness automatically.'
