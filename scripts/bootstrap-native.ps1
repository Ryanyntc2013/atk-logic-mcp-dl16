# Build the PINNED GPL-3.0 C++/libusb backend. Windows + VS2022 required.
[CmdletBinding()]
param(
  [switch]$SkipBuild,
  # Platform toolset to build with. Defaults to the locally installed VS2019 (v142)
  # toolset; if it is not present on this machine we fall back to the installed default.
  [string]$Toolset = 'v142'
)
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

# --- Local build compatibility fix (atk-logic-mcp-dl16) ---------------------------
# The pinned upstream links a prebuilt libusb STATIC library that carries /GL (LTCG)
# intermediate code produced by a NEWER MSVC front-end (19.39+). Toolchains older than
# that front-end (e.g. local VS2022 14.36 or VS2019 14.29 under VS2022) fail to link it
# with "LINK : fatal error C1900: Il mismatch" regardless of the selected toolset.
# We therefore link libusb through its DLL import library and stage libusb-1.0.dll next
# to the executables. This edits only the IGNORED checkout; the pinned commit content is
# never claimed to be modified. See docs/LOCAL-HANDOFF.md and docs/STATUS.md.
$CmakeLists = Join-Path $Dst 'CMakeLists.txt'
$StaticLibRef = 'VS2022/MS64/static/libusb-1.0.lib'
$ImportLibRef = 'VS2022/MS64/dll/libusb-1.0.lib'
$text = [System.IO.File]::ReadAllText($CmakeLists)
if ($text.Contains($StaticLibRef)) {
  $text = $text.Replace($StaticLibRef, $ImportLibRef)
  [System.IO.File]::WriteAllText($CmakeLists, $text)
  Write-Host '[note] Applied local libusb static->import-library build fix to ignored checkout.'
} elseif (-not $text.Contains($ImportLibRef)) {
  throw 'Pinned CMakeLists.txt has an unexpected libusb layout; refusing to guess.'
}
# -----------------------------------------------------------------------------------

if (-not $SkipBuild) {
  # Prefer the requested toolset only when it is actually installed on this machine;
  # otherwise fall back to the installed default (let CMake pick v143).
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
    } else {
      Write-Host "[info] Using installed toolset $Toolset."
    }
  }
  $configureArgs = @('-S', $Dst, '-B', (Join-Path $Dst 'build'), '-G', 'Visual Studio 17 2022', '-A', 'x64')
  if ($Toolset) { $configureArgs += @('-T', $Toolset) }
  & cmake @configureArgs
  if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed; check Visual Studio 2022 C++ tools' }
  cmake --build (Join-Path $Dst 'build') --config Release --parallel 4
  if ($LASTEXITCODE -ne 0) { throw 'Native backend build failed' }
  $Dll = Join-Path $Dst 'third_party\libusb\VS2022\MS64\dll\libusb-1.0.dll'
  if (-not (Test-Path $Dll)) { throw 'libusb-1.0.dll not found in pinned third_party; cannot stage runtime dependency' }
  Copy-Item -LiteralPath $Dll -Destination (Join-Path $Dst 'build\Release') -Force
  & (Join-Path $Dst 'build\Release\atkdl16_tests.exe')
  if ($LASTEXITCODE -ne 0) { throw 'Native upstream unit tests failed' }
}
Write-Host '[OK] Pinned backend checked out. Binary expected at external/ATK-Logic-Mcp/build/Release/atk-dl16.exe'
Write-Host 'IMPORTANT: do not run official ATK-Logic GUI concurrently with MCP.'
