# DL16-TASK-065 — METRO headless session-origin increment

**State:** DONE; complete requested tests and offline crop/replay PASS. Physical product UNVERIFIED / HIL_NOT_RUN.
**Scope:** independently authored host-only delta in sibling `timeSync-new`; no native, firmware, thresholds, B6 runtime, health-policy or hardware changes. Correct the stale offline B6 mock assertion and strengthen exact launch/query ordering, without changing recovery behavior.

- [Reviewable patch](../../scripts/patches/metro-headless-trigger-origin.patch) contains only changes against the preserved untracked baseline, not unrelated host work. Apply from the METRO root with `git apply --check <patch>` then `git apply <patch>`. Do **not** apply twice to the already updated local files.
- The patch includes the one-page METRO handoff at `docs/handoff/2026-10-11-dl16-task-065-trigger-origin.md`; local evidence is `timeSync-new/artifacts/DL16-TASK-065/`.
- Native percent-aligned Buffer semantics come from [TASK-013](../research/DL16-TASK-013-trigger-alignment.md); order-3 offset is post-trigger remaining with an explicitly bounded 7-sample diagnostic discrepancy. No third-party implementation copied; not a Stream crop rule.
- Actual frozen FAIL raw: uncropped CH3/CH7 late `[2000000]`; rematerialized each `[2000]`, delta 0.0 µs, measurement_valid true, original FAIL/R2 SHA-256 unchanged. This is an offline transform and archived ARM/STATUS replay, not new physical HIL or ≤1 µs certification.
- Final requested command: **PASS, 63 passed / 0 failed**. All six related files: **PASS, 191 passed / 0 failed**, no exclusions/skips. The initial stale mock expected an extra info query before first launch; production intentionally only warms up a failed retry. Exact event assertions now lock `info,capture_failed,info,capture_armed`, and the successful first launch asserts no info query. Previous baseline failures remain archived, not relabeled. Targeted compileall and editor diagnostics PASS.
- Baseline host commit `a1265070a513191669327b8ef241c664df480846`; exact pre-edit file SHA-256 values are in the patch header. No main-repo source files were staged because they already contained untracked unrelated work.

**Next:** Independent Reviewer checks this delta. B6 runtime reliability remains a separate mission. No live authorization, no S5Q execution. Hardware action counts all zero.
