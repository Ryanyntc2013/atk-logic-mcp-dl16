# DL16-TASK-054 — offline Order3 variant/range discriminator

State: **DONE (bounded offline deliverable)**; **HIL_NOT_RUN**. Base: `dc93274`. No commit requested. No hardware interaction, native/USB behavior changes, package installs, or public Stream capability changes.

## Objective and scope

Provide an import-safe reusable Python diagnostic for raw Order3 layout/range variants with explicit mode, profile, and request-depth context. Preserve exact raw bytes and raw uint40 fields; report signed40 only as a clearly labeled hypothesis. Values above a bounded diagnostic budget must not be available as unsigned crop/allocation inputs. Do not change existing Buffer convention. Stream stays UNKNOWN with no trusted crop or live capability.

## Implementation

- `src/dl16_mcp/order3_diagnostics.py`: validates exact 88-byte candidate layout, context and bounded budget; returns a bounded JSON-compatible report retaining exact raw hex, offset/count raw fields and null crop/valid sample count.
- `tests/test_order3_diagnostics.py`: versioned 10/30ms Stream cases, TASK051/052 Buffer-scope regression, malformed lengths, extreme uint40 values, invalid context, and no-crop assertions.
- `tests/vectors/task054-order3-diagnostic-v1.json`: portable compact case index; source observation vectors remain unchanged.
- Provenance recorded in `docs/SOURCES.md`.

The 88-byte layout (prefix2, offset5, sixteen count fields of5, suffix1) is a diagnostic hypothesis matching the supplied observations, not a normative parser contract. Buffer label reflects previously reviewed source convention only and does not cause cropping. Signed40 representation does not establish signed device semantics. Values within budget are not thereby validated as crop counts. Outputs are metadata-only and capped at 32 MiB equivalent unsigned candidate counts; Stream mode remains `UNKNOWN_STREAM_UNITS`.

## Acceptance evidence

Run:

- `.venv\Scripts\python.exe -m pytest -q tests\test_order3_diagnostics.py`: **4 passed in 0.04s**.
- `.venv\Scripts\python.exe -m pytest -q`: **286 passed in 10.41s**.
- `.venv\Scripts\python.exe -m compileall -q src`: exit 0.
- `git diff --check`: exit 0.

Hardware behavior is unverified; no new HIL claim. Next task suggestion: parent review this diagnostic, then separately define any future controlled HIL gate before interpreting Stream units/crops.
