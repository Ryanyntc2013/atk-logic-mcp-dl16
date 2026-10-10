[CmdletBinding()]
param([switch]$SkipNative)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 or change the launcher version' }
& .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Python environment setup failed' }
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Offline tests failed' }
if (-not $SkipNative) { & "$PSScriptRoot\bootstrap-native.ps1" }
Write-Host '[OK] Installation finished. Run: .\.venv\Scripts\dl16ctl.exe status'
Write-Host 'MCP command: .\.venv\Scripts\python.exe -m dl16_mcp.server'
