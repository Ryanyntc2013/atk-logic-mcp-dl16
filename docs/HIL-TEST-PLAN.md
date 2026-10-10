# Physical HIL acceptance plan — MUST be done on site

Current status: `HIL_NOT_RUN`. No DL16 has been accessed by this build of the scaffold.

## Preconditions

- Operator confirms exact product model (`DL16` or `DL16 Plus`), MCU/FPGA versions, OS and native CLI commit.
- Operator confirms known voltage range, common reference GND and which physical test point connects to each CH. Avoid unverified RF lens pins or unknown 5V/negative signals.
- Close official ATK-Logic GUI; confirm driver currently works before changing anything. Do not use Zadig automatically.
- Verify input is within hardware rating from official manual, threshold is appropriate for the logic family. Use independent oscilloscope/frequency generator if testing accuracy.
- Never bootloader / firmware update / raw vendor command during initial bring-up.

## Gate 0 — software and USB

1. `python -m pytest -q` => all tests pass.
2. `bootstrap-native.ps1` => CLI and native unit tests succeed.
3. `dl16ctl status` => correct real model/firmware and USB speed (record output and serial redacted).
4. If busy, stop and report `DEVICE_BUSY`; never force-close vendor GUI.

## Gate 1 — capture validity

1. Use known 1kHz square wave or device PWM0 correctly wired to CH0. Use immediate 1MHz/100ms/1.5V (or threshold appropriate to measured swing). Record expected duty and frequency.
2. Confirm `success=true`, `trigger_ack_received=true`, `capture_complete_received=true`, `data_integrity=COMPLETE` and complete samples for **every** requested channel.
3. Inspect stored samples/edges. Compare period against reference generator; correct measurement must not include residual post-depth samples.
4. Repeat at 2/20/100/200MHz **only if supported by identified model**; compare frequency invariant across rates.
5. Repeat with CH0 + CH1 + CH7 enabled. Record whether nonrequested channels are actually transferred and raw storage size.
6. Test no-transition input in immediate mode: `static_low` expected; do not classify lack of edges as missing device.

## Gate 2 — trigger and error recovery

1. Test `ch0:rising` against a controlled delayed-edge stimulus (separate power/no-edge intervals). Physical trigger should wait until edge, not only acknowledge command. If this fails, mark trigger `UNVERIFIED` or `FAIL` and disable HIL assertions relying on it.
2. Capture 30 times at 10MHz/100ms without unplugging, assert no ACK/Order6 missing, no partial sample and no stale bytes.
3. Disconnect while idle (operator initiated), ensure clear error then reconnect. Test USB remove during capture only with operator approval.
4. Validate host process timeout vs on-device 30s fixed watchdog. No claims of a 120s trigger wait until C++ core has been modified and tested.
5. Compare native output with official GUI's same signal (one app at a time).

## Gate 3 — synchronization accuracy (<1us application)

1. Connect **same clock or pulse generator** to both CH3 and CH7 via a proper splitter and equal-length leads, plus shared GND. Validate expected near-zero skew / bench offset using oscilloscope.
2. Sample at >=20MHz if supported. For better margin, 100MHz if supported. Record the sample quantization (50ns or 10ns respectively) and probe/threshold/system uncertainties separately.
3. Capture at least 1000 matched pulses across independent trials; compute signed delay min/max/mean/P95/P99/maxabs and missing pulse count using `logic_measure_skew`.
4. Add deliberate known signal delay, verify sign, matching and `expected_delay_ns` correction. Test one missing pulse, one extra pulse, a reset and drift windows.
5. Only then connect the wireless master/slave board outputs at the **physically confirmed channels**, verify independent reference scope at initial time and report distribution for <=1us requirement.
6. Never claim 1us hardware accuracy solely from waveform arithmetic or nominal sample interval.

## Reporting

Use the GitHub issue template `.github/ISSUE_TEMPLATE/hil-result.md`, unique task ID and SHA-256 of saved evidence. Result can be `HIL_PASS`, `HIL_FAIL` or `HIL_NOT_RUN`; separate instrument accuracy from target system performance.
