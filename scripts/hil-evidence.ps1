# Record an evidence manifest for one HIL task directory (artifacts/hil/DL16-TASK-xxx).
# Offline by default: writes environment.json (no device contact) and SHA256SUMS.txt.
# Device identity is read ONLY with -IncludeDeviceInfo (read-only 'info' CLI call) and the
# serial number is redacted before it is written.
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$TaskDir,
  [switch]$IncludeDeviceInfo
)
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Dir = (Resolve-Path -LiteralPath $TaskDir).Path
$Pin = '5fc47744c18c99f9ad0f554a965eb8cd1160c836'

$cli = $env:DL16_CLI_PATH
if (-not $cli) { $cli = Join-Path $RepoRoot 'external\ATK-Logic-Mcp\build\Release\atk-dl16.exe' }
$cliInfo = $null
if (Test-Path $cli) {
  $cliInfo = [ordered]@{
    path   = $cli
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $cli).Hash.ToLower()
  }
}

$deviceInfo = $null
if ($IncludeDeviceInfo) {
  if (-not $cliInfo) { throw 'Native CLI not found; cannot read device info.' }
  $raw = & $cli info 2>&1 | Out-String
  # Redact serial-number-like fields; keep everything else verbatim.
  $lines = $raw -split "`r?`n" | ForEach-Object {
    if ($_ -match '(?i)serial|\bsn\b') { ($_ -split ':', 2)[0] + ': <REDACTED>' } else { $_ }
  }
  $deviceInfo = @{ exit_code = $LASTEXITCODE; lines = @($lines | Where-Object { $_ -ne '' }) }
}

$env = [ordered]@{
  recorded_at_utc   = (Get-Date).ToUniversalTime().ToString('o')
  os                = [System.Environment]::OSVersion.VersionString
  powershell        = $PSVersionTable.PSVersion.ToString()
  repo_commit       = (git -C $RepoRoot rev-parse HEAD).Trim()
  repo_dirty        = [bool](git -C $RepoRoot status --porcelain)
  upstream_pin      = $Pin
  upstream_checkout = (git -C (Join-Path $RepoRoot 'external\ATK-Logic-Mcp') rev-parse HEAD 2>$null)
  native_cli        = $cliInfo
  device_info       = $deviceInfo
  device_info_read  = [bool]$IncludeDeviceInfo
}
$envPath = Join-Path $Dir 'environment.json'
$env | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $envPath -Encoding utf8

# Manifest of every file in the task directory (except the manifest itself).
$sums = Get-ChildItem -LiteralPath $Dir -Recurse -File |
  Where-Object { $_.Name -ne 'SHA256SUMS.txt' } | Sort-Object FullName |
  ForEach-Object {
    $rel = $_.FullName.Substring($Dir.Length).TrimStart('\', '/') -replace '\\', '/'
    '{0}  {1}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLower(), $rel
  }
$sumPath = Join-Path $Dir 'SHA256SUMS.txt'
Set-Content -LiteralPath $sumPath -Value $sums -Encoding ascii
Write-Host "[OK] environment.json and SHA256SUMS.txt written for $Dir ($(@($sums).Count) files)"
