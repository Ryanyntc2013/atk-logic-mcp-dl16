[CmdletBinding()]
param([switch]$Hardware)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
& .\.venv\Scripts\python.exe -m pytest -q
if($LASTEXITCODE -ne 0){throw 'Offline tests failed'}
if($Hardware){
  & .\.venv\Scripts\dl16ctl.exe status
  if($LASTEXITCODE -ne 0){throw 'Status query failed'}
  Write-Host 'Capture is deliberately NOT automatic. See docs/HIL-TEST-PLAN.md.'
}
