# Build the PINNED GPL-3.0 C++/libusb backend. Windows + VS2022 required.
[CmdletBinding()]
param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Dst = Join-Path $RepoRoot 'external\ATK-Logic-Mcp'
$Commit = '5fc47744c18c99f9ad0f554a965eb8cd1160c836'
if (-not (Test-Path $Dst)) {
  New-Item -ItemType Directory -Force (Split-Path $Dst) | Out-Null
  git clone https://github.com/gjjisadog/ATK-Logic-Mcp.git $Dst
  if ($LASTEXITCODE -ne 0) { throw 'Failed to clone upstream native backend' }
}
git -C $Dst fetch origin $Commit
if ($LASTEXITCODE -ne 0) { throw 'Failed to fetch pinned commit' }
git -C $Dst checkout --detach $Commit
if ($LASTEXITCODE -ne 0) { throw 'Failed to checkout pinned commit' }
if (-not $SkipBuild) {
  cmake -S $Dst -B (Join-Path $Dst 'build') -G 'Visual Studio 17 2022' -A x64
  if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed; check Visual Studio 2022 C++ tools' }
  cmake --build (Join-Path $Dst 'build') --config Release --parallel 4
  if ($LASTEXITCODE -ne 0) { throw 'Native backend build failed' }
  & (Join-Path $Dst 'build\Release\atkdl16_tests.exe')
  if ($LASTEXITCODE -ne 0) { throw 'Native upstream unit tests failed' }
}
Write-Host '[OK] Pinned backend checked out. Binary expected at external/ATK-Logic-Mcp/build/Release/atk-dl16.exe'
Write-Host 'IMPORTANT: do not run official ATK-Logic GUI concurrently with MCP.'
