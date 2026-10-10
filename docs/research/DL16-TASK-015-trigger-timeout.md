# DL16-TASK-015 — trigger timeout (`--trigger-timeout`)

**Date:** 2026-10-10
**Evidence tier:** LOCAL_HIL on the owner's DL16 Plus.

## Change

`execute_capture` already had a device watchdog timeout (default 30 s). A tracked
patch to the ignored CLI `main.cpp` exposes it as `--trigger-timeout <seconds>`;
`backend.capture` / `logic_capture` / `dl16ctl capture --trigger-timeout` / the MCP
`logic_capture` tool pass it through.

## HIL evidence

`ch0:rising` on an unwired CH0 (no edge), `--trigger-timeout 3`:

```
success=false error_code=CAPTURE_TIMEOUT elapsed_s=3.7
```

A gated capture that cannot be satisfied returns in ~3 s instead of the default 30 s.

## Notes

- Bounded and idempotent tracked patch; pinned commit content never claimed modified.
- Offline test covers the command plumbing (`tests/test_backend.py`).
- Does not by itself prove gating (covered by DL16-TASK-010/011).
