# DL16-TASK-024 — observed completion-before-data regression

Objective: preserve TASK-023 parsed-message evidence as a versioned offline vector and ensure packet completion markers cannot replace sample-count validity. Allowed scope: offline vector, harness regression and provenance; no receive-policy/device changes or live capture.

The vector records `[6,6,6,4,5,5,5,5]`, one 16,384-byte read and zero samples before/after crop from TASK-023. It is a derived parsed-order sequence, NOT raw USB bytes, a capture replay or proof of stale Complete ownership. The test deliberately supplies misleading success/COMPLETE flags and verifies the existing harness still rejects zero samples. This guards evidence acceptance, not native parser/transport behavior; no native fix is claimed.

Baseline `0b8604026197f3901b975cf096f014726f08d458`. Validation: `.venv\Scripts\python.exe -m pytest -q` — **135 passed in 5.31s**; `.venv\Scripts\python.exe -m compileall -q src scripts` and `git diff --check` passed. Delivery DONE (offline acceptance regression). Original operator LOCAL-HANDOFF modification preserved.

Next native change needs an explicit design: protocol has no demonstrated acquisition generation ID; merely ignoring Complete until sample counts fill could wait on mixed-generation data and falsely validate a waveform. Instrument pre-arm flush/wake and message arrival phases or add offline replay of actual frame bytes before choosing completion policy. No automatic reset or additional drain adopted. One-shot remains default and B6 retry retained. Hardware HIL_NOT_RUN for this task.
