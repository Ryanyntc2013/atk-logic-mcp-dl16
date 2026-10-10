# LHX369963/dl16-cli — high-value feature adoption (DL16-TASK-005)

**Date:** 2026-10-10
**Source reviewed:** LHX369963/dl16-cli@8d7c209 (`README.md`, `docs/usage/*`).
**Constraint:** LHX has **no explicit LICENSE**; adopt **behavior/design only**, no
code copying. The pinned CPP backend stays authoritative for live USB. Evidence
discipline unchanged.

## Feature map

| LHX capability | Value | Our status | Decision |
|---|---|---|---|
| `pwm start/stop` + `pwm verify` (fixed PWM0->input loopback) | high | codec + `dl16-pwm` tool; live LOCAL_HIL | **ADOPTED** (verify workflow still manual) |
| Persistent JSONL `session` (pwm/capture/stream over one USB link) | high — avoids per-command reinit | not present; B6 retry mitigates the post-capture open failure | **DEFER** (needs a native persistent process) |
| `capture stream` (incremental, interruptible, rate limits) | high | buffer only | **DEFER** (native backend) |
| Trigger position (`--trigger-position`), `--trigger-timeout`, multi-channel `--trigger-states` | high | only `chN:edge`; position hardcoded 10%; gating not functional (B3) | **DEFER / investigate** (native param) |
| Hardware RLE | medium | not enabled | **DEFER** |
| `capture measure` (frequency/duty) | high | `logic_measure_pwm` | **ADOPTED** |
| `capture filter` (drop short pulses -> new capture) | medium | **`logic_filter` added now** | **ADOPTED** |
| `capture search` (multi-channel conditions) | medium | **`logic_search` added now** | **ADOPTED** |
| `capture export` CSV / edges / VCD (streaming) | high | **`logic_export` VCD + edges + sample CSV now; overwrite-protected** | **ADOPTED** |
| Native decoders: UART (5–9 bits, parity, stop, invert), SPI modes/bit order | medium | **in-repo `decoders.py` (UART/I2C/SPI) added now**, MCP+CLI wired | **ADOPTED** |
| sigrok integration (`capture sigrok`) | medium | not present | **PROPOSE / optional** |
| Capture dir `manifest.json` + `wire.bin` (raw packets) + `channel-NN.bin` | medium | `meta.json` + `chNN.bits` + `edges.json` (raw bits kept; raw USB packets not) | **ADAPT** (consider retaining raw packets) |
| `--sample-index` default pick, `--force` overwrite protection | low | fixed rate map; new dir per capture | **ADOPTED (overwrite protection)**; sample-index fixed |
| Silent success output; measurements print only requested values | low | returns JSON | acceptable |
| `skills/dl16-cli` Codex Skill packaging | medium | agent-facing tool reference `docs/MCP-TOOLS.md` added | **ADOPTED (as docs)** |

## Adopted now (this change)

`logic_export(capture_id, channel, fmt="vcd"|"edges", polarity, atkdl_file, out_name)`
— offline, edge-based writers in `analysis.py` (`to_vcd`, `to_edges_csv`), exposed as an
MCP tool and `dl16ctl export`. Output is written to `DL16_DATA_DIR/exports/` and the
tool returns the path + byte size (never the full content), keeping MCP messages
bounded and enabling external tools (sigrok, waveform viewers).

## Proposed follow-up tasks

- `DL16-TASK-006` — `logic_filter` (drop pulses shorter than N samples) + `logic_search`
  (multi-channel conditions) offline.
- `DL16-TASK-007` — richer offline decoders (UART parity/stop/invert, SPI modes/bit order).
- `DL16-TASK-008` — native persistent session transport (reliability + multi-op).
- `DL16-TASK-009` — trigger position/timeout/multi-condition (native param) once gating
  semantics are understood (see B3).

## Non-goals

Do not port LHX source; do not change the pinned live backend without a reviewed
patch/fork; do not weaken evidence tiers or the HIL gates.
