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
# All local build compatibility/feature changes live in ONE reviewable patch file applied on
# top of the pinned commit. It touches CMakeLists.txt (libusb import library, C1900 fix),
# core/src/protocol.cpp (10-byte gated SimpleTrigger, DL16-TASK-010/011) and cli/main.cpp
# (--trigger-position DL16-TASK-012, multi-channel AND DL16-TASK-014, --trigger-timeout 015).
$Patch = Join-Path $RepoRoot 'scripts\patches\atk-dl16-local-build.patch'
$SessionPatch = Join-Path $RepoRoot 'scripts\patches\atk-dl16-session.patch'
if (-not (Test-Path $Patch)) { throw "Local patch missing: $Patch" }
if (-not (Test-Path $SessionPatch)) { throw "Session patch missing: $SessionPatch" }

if (-not (Test-Path $Dst)) {
  New-Item -ItemType Directory -Force (Split-Path $Dst) | Out-Null
  git clone https://github.com/gjjisadog/ATK-Logic-Mcp.git $Dst
  if ($LASTEXITCODE -ne 0) { throw 'Failed to clone upstream native backend' }
}
git -C $Dst fetch origin $Commit
if ($LASTEXITCODE -ne 0) { throw 'Failed to fetch pinned commit' }
git -C $Dst checkout --detach $Commit
if ($LASTEXITCODE -ne 0) { throw 'Failed to checkout pinned commit' }

# `checkout --detach` keeps local modifications, so force the ignored checkout back to the
# pinned tree before applying the patch. This makes the result reproducible from clean state.
# Only the IGNORED external checkout is reset; no upstream history is rewritten.
git -C $Dst reset --hard $Commit | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Failed to reset ignored checkout to pinned commit' }
# The protocol header is intentionally introduced by the session patch, but it is untracked
# in the ignored checkout and therefore survives `git reset --hard`. Remove only that
# patch-owned path before applying the tracked patch so repeated clean builds are reproducible.
$SessionHeader = Join-Path $Dst 'cli\session_protocol.h'
if (Test-Path $SessionHeader) { Remove-Item -LiteralPath $SessionHeader -Force }

git -C $Dst apply --check $Patch
if ($LASTEXITCODE -ne 0) { throw "Local patch does not apply cleanly to pinned commit: $Patch" }
git -C $Dst apply $Patch
if ($LASTEXITCODE -ne 0) { throw 'Failed to apply local patch' }
Write-Host "[note] Applied local patch to ignored checkout: $(Split-Path $Patch -Leaf)"

git -C $Dst apply --check $SessionPatch
if ($LASTEXITCODE -ne 0) { throw "Session patch does not apply after the base patch: $SessionPatch" }
git -C $Dst apply $SessionPatch
if ($LASTEXITCODE -ne 0) { throw 'Failed to apply persistent-session patch' }
Write-Host "[note] Applied persistent-session patch to ignored checkout: $(Split-Path $SessionPatch -Leaf)"
$DiagnosticsPatch = Join-Path $RepoRoot 'scripts\patches\atk-dl16-diagnostics.patch'
git -C $Dst apply --check $DiagnosticsPatch
if ($LASTEXITCODE -ne 0) { throw 'Diagnostics patch check failed' }
git -C $Dst apply $DiagnosticsPatch
if ($LASTEXITCODE -ne 0) { throw 'Diagnostics patch apply failed' }
$PrearmPatch = Join-Path $RepoRoot 'scripts\patches\atk-dl16-prearm.patch'
git -C $Dst apply --check $PrearmPatch
if ($LASTEXITCODE -ne 0) { throw 'Prearm telemetry patch check failed' }
git -C $Dst apply $PrearmPatch
if ($LASTEXITCODE -ne 0) { throw 'Prearm telemetry patch apply failed' }
$LifecyclePatch = Join-Path $RepoRoot 'scripts\patches\atk-dl16-experimental-lifecycle.patch'
git -C $Dst apply --check $LifecyclePatch
if ($LASTEXITCODE -ne 0) { throw 'Experimental lifecycle patch check failed' }
git -C $Dst apply $LifecyclePatch
if ($LASTEXITCODE -ne 0) { throw 'Experimental lifecycle patch apply failed' }
$PwmPatch = Join-Path $RepoRoot 'scripts\patches\atk-dl16-session-pwm.patch'
if (Test-Path $PwmPatch) {
  git -C $Dst apply --check $PwmPatch
  if ($LASTEXITCODE -ne 0) { throw 'PWM session patch check failed' }
  git -C $Dst apply $PwmPatch
  if ($LASTEXITCODE -ne 0) { throw 'PWM session patch apply failed' }
  Write-Host "[note] Applied PWM session patch to ignored checkout: $(Split-Path $PwmPatch -Leaf)"
}

$StopPatch = Join-Path $RepoRoot 'scripts\patches\atk-dl16-stop-observation.patch'
git -C $Dst apply --check $StopPatch
if ($LASTEXITCODE -ne 0) { throw 'Stop observation patch check failed' }
git -C $Dst apply $StopPatch
if ($LASTEXITCODE -ne 0) { throw 'Stop observation patch apply failed' }

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
