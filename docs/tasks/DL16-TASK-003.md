# DL16-TASK-003 — local native build reproducibility (toolset + libusb linking)

**Owner:** local Codex/Cursor agent on Windows.
**State at issue:** DONE (offline build + read/status level).
**Depends on:** `DL16-TASK-001` (device presence/status). Does not change protocol behavior.

## Mission

Make the pinned native backend build reproducibly on a local Windows workstation whose
MSVC toolsets are **older** than the toolset that produced the bundled prebuilt libusb
static library, without editing the pinned upstream content and without silently
changing device-facing behavior.

## Finding

`scripts/bootstrap-native.ps1` failed at link time on a machine with only VS2022
`MSVC 14.36` and the VS2019 `v142 14.29` toolset:

```text
libusb-1.0.lib(core.obj) : found MSIL .netmodule or module created with /GL; link with /LTCG
LINK : fatal error C1900: Il mismatch between 'P1' version '20240319' and 'P2' version '<current>'
```

`P1` was **constant** (`20240319`) across the default `v143` build (`P2=20221215`) and a
`v142` build (`P2=20210202`). It therefore belongs to the bundled
`third_party/libusb/VS2022/MS64/static/libusb-1.0.lib`, whose `/GL` (LTCG) intermediate
code was produced by a **newer MSVC front-end (>= 19.39)**. Any older local toolset
cannot statically link it; selecting the VS2019 (v142) toolset makes it strictly worse.
This is not a toolset-selection problem and was not visible on CI (`windows-latest` ships
a newer MSVC).

## Decision

Link libusb through its **DLL import library** (`VS2022/MS64/dll/libusb-1.0.lib`), which
carries no LTCG intermediate code, and stage `libusb-1.0.dll` next to the executables.
The pinned commit content is never modified; the change is applied to the IGNORED
checkout by the tracked bootstrap script and is idempotent. The import library's
`LIBUSB_CALL`-only header makes this ABI-safe.

Additionally, `bootstrap-native.ps1` now defaults `-Toolset` to the locally installed
VS2019 toolset (`v142`) and, when that toolset is absent, emits a warning and falls back
to the machine default (`v143`). `-Toolset auto` forces the CMake default.

## Acceptance / evidence (this workstation)

| Check | Command | Result |
|---|---|---|
| Offline suite | `python -m pytest -q` | 17 passed |
| Compile | `python -m compileall -q src` | OK |
| Native build | `scripts/bootstrap-native.ps1` | `[info] Using installed toolset v142.` |
| Native tests | `atkdl16_tests.exe` | 28/28 passed |
| Fallback path | `scripts/bootstrap-native.ps1 -Toolset v140` | warning + v143, 28/28 passed |
| Device status | `dl16ctl status` | connected:true, ready:true, DL16 Plus, MCU v1.9, FPGA v2.22, 16ch |
| Bounded capture | `dl16ctl capture` CH0/immediate/20MHz/20ms/1.6V | REAL_HARDWARE, COMPLETE, ack+complete=true |

HIL_PASS is **not** issued: the capture was not compared against an independent
instrument, and physical trigger gating was not exercised.

## Out of scope

RLE/stream, sample-rate index maps, 9B/10B trigger frames, driver changes, firmware,
and upstream static-libusb replacement by a newer-toolset prebuilt library.
