# DL16-TASK-053 — bounded Stream depth comparison

Objective: test TASK052 fixed16 versus round32 hypotheses using existing user hardware authorization and confirmed CH8/CH14 safe PWM loopbacks, shared ground, threshold1.6V. Internal diagnostic only; public Stream remains blocked.

Plan: 20MHz/10ms then30ms, immediate/noRLE, same fixed100ms receive deadline and32MiB cap. Preserve exact TX, device profile, RX reads, packed data and hashes. Stop first missing ACK/Order3/Order6, changed profile, short reads, deadline/cap/error or failed cleanup; no retries, reset, firmware, drivers or wiring changes. Do not crop or claim COMPLETE. Evidence artifacts/hil/DL16-TASK-053.

Predictions requested25000/75000 bytes per channel: fixed16=>25016/75016; round32=>25024/75008. Matching fixed16 does not establish Order3 units or valid sample alignment. Results recorded below; no completeness/crop promotion.

## Offline follow-up result (child, no new HIL/no commit)

State: **DONE observation / BLOCKED public Stream semantics**. Parent supplied
physical archives; child used only bounded read-only Python/native source analysis.
Original TASK051 stream-01/02 and TASK053 depth-10/30 files remain unchanged.
Reproducer `tests/task053_observation.py` reuses TASK051 parser/converter and
32MiB cap. Versioned profiles `tests/vectors/task053-depth10-observation-v1.json`
and `task053-depth30-observation-v1.json` retain hashes, exact counts and UNKNOWN
alignment/tails/validity. All16 packed files reconstruct byte-for-byte from raw.

### Exact records and suffixes

10ms: requested200000 samples/25000 packed bytes; all16 channels **25008 bytes**,
13 packets/channel (12*2032+624); all end in exactly8 AA bytes. 50 reads*16384,
819200 USB bytes,819608 framed file bytes; status0, no shorts. Messages:
Order1=208,Order2=188,Order3=1,Order4=1,Order6=2; desync413714. ACK read1,
Order3 read2, both Order6 in read50. Raw SHA256
`cceaaf14ff3a0a5836a351995fdd509a158c415b85251621d699860c5c2453e4`.

30ms: requested600000 samples/75000 packed bytes; all16 channels **75008 bytes**,
37 packets/channel (36*2032+1856); all end in exactly8 AA bytes. 98 reads*16384,
1605632 USB bytes,1606424 framed file bytes; status0, no shorts. Messages:
Order1=592,Order2=184,Order3=1,Order4=1,Order5=4,Order6=2; desync397098. ACK read1,
Order3 read2, both Order6 in read98. Raw SHA256
`9b1330e62b8d8e481c02bf2b02f0db9db7a8f92402ce2c351c971318d8c26301`.
Cleanup Stop/PWM-stop successful by parent summary, not physical idle certification.

### TX construction/profile and Order3 conflict

Both cached-open profiles: VID6790/PID65484 (1A86:FFCC), model enum2/name DL16 Plus,
MCU19,FPGA222,hardware2,level1,16 channels,USB-speed enum2. Profile authority is
CACHED_DEVICE_OPEN_QUERY_NOT_INDEPENDENT_VERIFICATION. Not a calibrated identity.

TX authority HOST_CONSTRUCTED_NOT_BUS_OBSERVED. Existing reference demultiplexing
and pinned frame CRC over command/length/payload verify logged constructed frames:
parameter command0x11, payload10ms `001006400d0300000000000000`,30ms
`001006c0270900000000000000`; flag00 (Stream/noRLE),threshold0x10,rate6,
uint40 depths200000/600000,trigger depth0. Both trigger0x12 payload
`00000000f00000f001` = only CH8/14 enabled, immediate01, unchanged9-byte schema.
No TX USB bus observation; construction is not firmware acceptance proof.

Order3 depth10 offset17, all16 fields `f0ffffffff` = **2^40-16**, not unsigned
sample byte counts; depth30 offset21, all16 `f8ffffffff` = **2^40-8**.
Their signed40 interpretations would be -16/-8, but **signed units/sentinel meaning
remain unproven**. Do not modify parser live interpretation or convert them into
crop offsets. TASK05120ms field25001/offset22 differs qualitatively.

### Cross-three hypothesis conclusions / safe gate

20ms:50016 bytes/channel,16 AA suffix,field25001. 10ms:25008/8AA;
30ms:75008/8AA. **Fixed16 disproven** at10/30. **Round-up32 disproven** at10
(predicted25024,observed25008);30 alone matching75008 is non-discriminating.
**Fixed8 disproven** at20. Proposed `field*2+6` fails all three as an unsigned
relationship: at20 gives50008, NOT50016; new enormous fields also fail. Substituting
signed40 would yield negative values, not actual lengths. No arithmetic fit selects
valid samples, aligned start or a stripping rule. All16 transmission persists with
CH8/14-only constructed trigger; budget assumptions must use observed all16 until
an evidence-backed physical selection contract exists.

Stored interior CH8/CH14 period distributions include20000/10000 spacing; AA suffix
adds31 two-bit intervals for10/30 and63 for20. No new calibrated PWM/valid-prefix
acceptance is claimed. Preserve whole files, report null valid_sample_count.

**Stop conclusion:** public Stream remains STREAM_TAIL_UNVERIFIED. Next safe
implementation gate is an OFFLINE schema/range discriminator for Order3 variants:
preserve raw40 fields and optional signed hypothesis separately, reject impossible
unsigned counts before allocation/cropping, version/model-tag diagnostics, and
multi-depth failure vectors. No promote/crop when units/sentinel meaning unknown.
Tail handling must remain preserve-all pending independent documented format or
physical alignment proof; no further HIL authorized/executed by this child.

### Validation

Exact command `.venv\\Scripts\\python.exe -m pytest -q tests\\test_task051_observation.py tests\\test_task053_observation.py tests\\test_stream_evidence.py`:
18 passed after correcting a hypothesis-test arithmetic mistake (25001*2+6=50008).
Ruff checks of new helper/tests pass; `git diff --check` passes. Portable vectors
assert negative hypotheses, UNKNOWN and exact TX fields; optional archive tests
reconstruct actual files and CRCs, skip when ignored physical archives absent.
No fabricated HIL data. No commit.
