# DL16-TASK-055 — genuine experimental asynchronous Stream

State: **DONE offline implementation / NEEDS_HUMAN_HIL**. Base `a252818`; no commit requested. Child OFFLINE ONLY / **HIL_NOT_RUN**, parent sole hardware owner. No USB, PWM, reset, firmware, endpoint clearing or driver operations executed.

## Objective, scope, plan

Read AGENTS, LOCAL-HANDOFF, SOURCES, mandatory TASK002/LHX and TASK049–054. Compare pinned channel selection/termination/crop narrowly; independently implement opt-in untrusted Stream using actual native parameters, TASK049 single-owner control and TASK050 incremental writer. Preserve unknown tails/all16 channels; test actual production receive/control/storage with injected USB-free transport, rebuild tracked bootstrap stack, run targeted/full tests. No trusted Stream promotion, RLE, edges, one-shot/Buffer changes or unlicensed code copying.

## Narrow pinned source comparison

- LHX `8d7c209c1e3b13923620bb34cec915291a749612`, `dl16_cli/streaming.py` lines37–113: filters ChannelData to requested file channels, terminates when requested packed depth is written, discards same-packet suffix and truncates files to common retained depth. Its ~8/~12-byte comment is reported observation, not our crop contract. `capture.py` lines113–123 decodes received channel ID/body without proving physical selection. These source facts were read only; no code copied, translated or bundled.
- VENDOR `0dff562d24436def2bec3791684f1911997b9e35`, `pv/thread/thread_work.cpp`: Order3 byte-count crop guarded by Buffer (230–278), Stream Order6 capacity/termination (321–345), ChannelData received ID used directly. No Stream AA-strip contract established.
- CPP `5fc47744c18c99f9ad0f554a965eb8cd1160c836` CaptureEngine accumulates/crops SampleStore; its general byte-count naming is not verified Stream semantics. TASK051/053 parent evidence received all16 with CH8/14 trigger selection. This path therefore bypasses CaptureEngine/SampleStore entirely for experimental Stream, writes all actual16, stops on first parsed Order6 or deadline/cancel/error/cap, never assumes requested depth proves completeness.

Source comparison is SOURCE_REVIEWED, not local HIL. LHX source copies used only as ignored read-only research in `artifacts/research/TASK052`; no reuse permission inferred.

## Implemented boundaries

Tracked `scripts/experimental_stream.h` contains shared production receive/control loop; tracked `scripts/patches/atk-dl16-experimental-stream.patch` connects it to actual native owner. Bootstrap copies header and applies patch after writer foundation. `experimental_stream_v1` advertised only by this connected worker; Python rejects older workers before dispatch. Public MCP/service/backend expose `logic_stream_start`, `logic_stream_poll`, `logic_stream_cancel`.

Start requires `experimental_opt_in=True`, `safety_confirmation="CONFIRMED_SAFE_WIRING_GUI_CLOSED"`, explicit 1–2 trigger channels, supported1/2/4/5/10/20MHz,1–30000ms and confirmed threshold. Immediate9B trigger, zero position, Stream flag (not Buffer), no RLE/mode override. Native revalidates before dispatch. Actual all16 channel payloads preserved, including unrequested channels. No synthetic live command or Buffer alias.

All16 requested packed size plus1MiB reservation must fit200MiB; actual packed storage capped199MiB, reserving1MiB for bounded metadata. Thus20MHz/30s is rejected (all16 ~1.2GB), not silently downsampled;30s at low rates remains possible. Raw RX logging is intentionally disabled on this public path (optional facility not added), avoiding a second disk budget. Reads16KiB, parser packets max65535B, append<=64KiB; no full-capture RAM/edge accumulation. Flushed per-chunk writes provide synchronous disk backpressure. Control queue8, one owner/operation/result; poll/cancel cannot cross operation kind. EOF cancels/joins; Python close uses correct operation kind.

Receive deadline is requested duration from successful trigger write, <=30s. Reads<=10ms clipped to remaining deadline; parameter/trigger/Stop writes<=50ms, existing DAC settle30ms. Cancel before trigger avoids trigger write. Owner attempts documented Stop on every started shared-loop path before finalization. Existing Device open/query/close lifecycle remains; no new reset/recovery/extra query. Opening/OS scheduling/filesystem writes can exceed cooperative bounds; no hard real-time or physical idle claim. First short-bank RX ends SHORT_RX without reinterpretation; packed prefix remains untrusted. No raw logging means the unconverted short bytes are counted, not recoverable in this path.

Artifacts: exclusive new UUID directory, all16 `chN.packed.bin`, `stream_meta.json`; `dl16-incremental-packed/v1` is not analysis registered. Every terminal state remains INCOMPLETE, UNKNOWN tails, null valid samples, no edges/crop. Source extent indices describe stored packed positions only; rate Hz unchanged, no invented physical ns alignment. Source declaration UNKNOWN even on live receive; SYNTHETIC_OFFLINE only in test seam. Raw Order3 hex<=512chars retained in bounded final response, never interpreted as crop. ACK/Order6 counts/Stop write result are observations, not gating/completeness or HIL_PASS. `result.success=false` deliberately means no trusted capture; outer `ok=true` means control/observation completed. Disk metadata updates are not crash-atomic/power-loss durable.

## Acceptance and exact results

- `powershell -File scripts\bootstrap-native.ps1 -SkipTests`: exit0, repeated full tracked patch builds. Upstream device-open tests NOT run.
- `cmake -S tests\native -B tests\native\build`: exit0.
- `cmake --build tests\native\build --config Release --target dl16-experimental-stream-test dl16-incremental-writer-test dl16-async-buffer-test --parallel 4`: exit0.
- `.venv\Scripts\python.exe -m pytest -q tests\test_experimental_stream.py tests\test_incremental_writer.py tests\test_async_buffer.py`: **29 passed in1.68s**.
- `.venv\Scripts\python.exe -m pytest -q`: **289 passed in10.44s**.
- `.venv\Scripts\python.exe -m compileall -q src`; `git diff --check`: exit0.
- `.venv\Scripts\python.exe -m ruff check tests\test_experimental_stream.py tests\test_incremental_writer.py`: passes. Existing affected production modules retain pre-existing lint findings; not unrelatedly rewritten.
- Native CLI SHA256 `041AF6AFC62162D833F56EDC4DB85B4C63B9EB3964A04BDA2C9788DC1FBD167B`.

Actual production parser/Stream mode/writer/dispatcher tests prove all16 actual ChannelData persisted with AA retained while operation still running, cooperative cancel/Stop, EOF cancellation, busy/wrong-ID rejection, final INCOMPLETE/null/UNKNOWN. Host tests cover explicit confirmation/prelaunch all16 budget, routed start/poll/cancel and no relabel; older-worker guard and actual CLI hello/missing-opt-in tests never open USB. No physical transport mock is represented as HIL. CI selector updated, remote CI NOT run. Ignored build/test logs `artifacts/task055-{build,harness,full}.txt`.

## Parent-only single bounded HIL invocation

NOT executed by child. Only parent may invoke, after reviewing standard Device lifecycle and confirming existing authorized CH8/14 wiring/shared ground/1.6V, GUI closed and no competing owner. Use current repository worker, session mode; do not launch alongside an existing native session. Do not configure PWM or change wires from this recipe.

Exactly one `logic_stream_start(experimental_opt_in=True, safety_confirmation="CONFIRMED_SAFE_WIRING_GUI_CLOSED", channels=[8,14], sample_rate_hz=20000000, duration_ms=20, threshold_voltage=1.6)`. Immediately request `logic_stream_cancel(operation_id=<ID>)`, poll bounded status until finished, then `logic_session_close()`. Capture completion racing cancel is NOT cancellation acceptance; no retry to force it. For20ms all16 nominal800000B plus bounded unknown extras,199MiB runtime hardcap remains. Retain request timestamps, worker hash/PID, all16 file/meta hashes, raw Order3/final reason/ACK/Order6 and Stop/close results under ignored `artifacts/hil/DL16-TASK-055/`. Stop on USB/write/short/cap/deadline/failed cleanup; never reset/retry automatically. Every artifact must remain INCOMPLETE/UNKNOWN and fail trusted analysis. Parent decides further HIL; no automatic roadmap promotion.

Next suggested TASK056: owner physical cancellation/termination evidence and error-path recovery review without resets; tail/crop/alignment still unresolved.

Parent bounded HIL: repository backend stream_start20MHz/20ms CH8/CH14 then immediate cancel finished CANCELLED, stored_bytes0, INCOMPLETE/UNKNOWN, analysis_ready=false, both Stop fields true. close_session success=true. Evidence artifacts/hil/DL16-TASK-055/records.json, journal, native-hash.txt and returned artifact_directory. Cancellation before any data is verified, not sustained USB throughput or incremental physical data acceptance. No retry or PWM setup in this gate. Overall experimental receive path still requires separate normal receive HIL.
