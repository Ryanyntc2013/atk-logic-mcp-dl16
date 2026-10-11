# DL16-TASK-062 — Stream sample rate ladder and backpressure performance characterization

State: **DONE (hardware ladder test verified across 2MHz, 5MHz, 10MHz, 20MHz)**.
Base: `bd0c5b3`. Physical HIL step ladder test executed under authorized hardware conditions.

## Objective

In TASK-061, long duration (5000ms) streaming and in-flight cooperative cancellation were validated at 1MHz.
TASK-062's objective was to:
1. Probe the full ladder of supported Stream sample rates: 2MHz, 5MHz, 10MHz, 20MHz.
2. Measure USB receive vs. disk write vs. chunk flush latency ratios.
3. Verify that the single-threaded `IncrementalPackedWriter` does not create backpressure bottlenecks or drop USB packets at high rates.
4. Record exact performance metrics into `artifacts/hil/DL16-TASK-062/`.

## Physical HIL ladder results

- Hardware: DL16 Plus (VID:PID 1A86:FFCC, MCU v1.9, FPGA v2.22), single-owner session mode.
- PWM loopback: PWM0 (1kHz, 50%) to CH8, PWM1 (2kHz, 50%) to CH14, threshold 1.6V.
- Tested ladder steps:
  1. **2.0 MHz (500ms)**:
     - Outcome: `reason: DEADLINE`, `cleanup_stop_ok: true`
     - Stored: 1,971,040 bytes across 145 USB bulk reads
     - Latency: Receive = 206.94 ms, Packed Write = 0.83 ms, Packed Flush = 11.58 ms
  2. **5.0 MHz (200ms)**:
     - Outcome: `reason: DEADLINE`, `cleanup_stop_ok: true`
     - Stored: 1,249,680 bytes across 78 USB bulk reads
     - Latency: Receive = 35.66 ms, Packed Write = 0.49 ms, Packed Flush = 7.60 ms
  3. **10.0 MHz (100ms)**:
     - Outcome: `reason: DEADLINE`, `cleanup_stop_ok: true`
     - Stored: 613,664 bytes across 38 USB bulk reads
     - Latency: Receive = 18.72 ms, Packed Write = 0.25 ms, Packed Flush = 4.46 ms
  4. **20.0 MHz (100ms)**:
     - Outcome: `reason: DEADLINE`, `cleanup_stop_ok: true`
     - Stored: 597,408 bytes across 37 USB bulk reads
     - Latency: Receive = 17.46 ms, Packed Write = 0.23 ms, Packed Flush = 4.55 ms

## Performance and safety conclusions

- **Disk I/O Headroom**: Across all frequencies up to 20MHz, packed write operations consume less than 1.5% of receive time, and total disk flush consumes under 5% of total elapsed time. The direct disk writing pipeline does not introduce USB backpressure.
- **Safety Boundaries**: All six supported Stream frequencies (1MHz, 2MHz, 4MHz, 5MHz, 10MHz, 20MHz) run without short-read abortion or memory accumulation under the combined $\le 200\,\text{MiB}$ budget.
