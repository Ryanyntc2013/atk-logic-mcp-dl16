# DL16-TASK-002 gate B1 — sample-rate index verification (2026-10-10)

Evidence tier: **LOCAL_HIL** on the owner's DL16 Plus (MCU v1.9, FPGA v2.22, USB 2.0).
Wiring: PWM0 -> CH0 loopback (operator-confirmed). PWM started at a known frequency;
CH0 captured; measured samples/period compared to
`period_count * sample_rate / 200_000_000`.
Full evidence (ignored): `artifacts/hil/DL16-TASK-002/b1-rate-index.json`.

## Results

| sample rate | CPP index | PWM freq | expected samples/period | measured | match |
|---:|---:|---:|---:|---:|:--:|
| 1 MHz | 1 | 1 kHz | 1000 | 1000 | yes |
| 5 MHz | 4 | 10 kHz | 500 | 500 | yes |
| 10 MHz | 5 | 100 kHz | 100 | 100 | yes |
| 20 MHz | 6 | 100 kHz | 200 | 200 | yes |
| 40 MHz | 8 | 100 kHz | 400 | 400 | yes |
| 50 MHz | 9 | 100 kHz | 500 | 500 | yes |
| 100 MHz | 10 | 1 MHz | 100 | 100 | yes |
| 200 MHz | 11 | 1 MHz | 200 | 200 | yes |
| 250 MHz | 12 | 1 MHz | 250 | 250 | yes |
| 500 MHz | 13 | 1 MHz | 500 | 500/501 | yes (±1 sample jitter) |
| 25 MHz | 7 | 1 MHz | 25 | 25 | yes |

`period_ns_jitter_rms = 0` for every case except 500 MHz (±1 sample).

## Key findings vs research R1

- The pinned **CPP** `sample_rate_to_code` table is **correct on this device**:
  indices 1,4,5,6,7,8,9,10,11,12,13 all produced the expected rate.
- **Index 7 (25 MHz) works here** with a clean 25 samples/period — it does **not**
  reproduce LHX's "index 7 returned no type-1 samples".
- **Index 13 (500 MHz) works here** on a **DL16 Plus** (CPP grants 500 MHz only to
  Plus). This does not reproduce LHX's "500 MHz -> index 0 on DL16".
- The R1 **SOURCE_CONFLICT** is therefore not reproduced on this hardware: the
  difference is attributed to a different model/firmware (unproven), and **no live
  encoding was changed**.

## Status

- B1: `LOCAL_HIL`, sample-rate index map confirmed for this unit.
- 25/500 MHz were tested only because this operator-confirmed unit accepted them;
  index-7 no-data handling still fails closed upstream (no silent fallback).
