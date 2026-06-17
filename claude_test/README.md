# claude_test

Debug, exploratory, and diagnostic scripts. Not part of CI/CD.

Production-quality tests live in `tests/` (if present).

## Index

| File | Purpose | Findings |
|------|---------|----------|
| `test_connection.py` | RS485 smoke test: read model, version, and current position from the Panasonic MINAS A6 amplifier over `/dev/ttyUSB0`. | 2026-04-14: PASS — reads MDDLN45SL / Ver.1.016 / position. Use as the first sanity check after any wiring or amp parameter change. |
| `diagnose_amp_state.py` | Read-only diagnostic: identity, Pr0.01 / Pr3.04 / Pr3.00, 2-second feedback drift, and raw input-signal frame. | 2026-04-14: caught a leftover Pr3.04 = -5 after an Err16.0 overload incident, which was the root cause of "amp not moving" symptoms. Run before motion tests and any time the rail behaves unexpectedly. |
| `check_input_signals.py` | Read-only inspection of SI1~SI10 function assignments (Pr4.00~Pr4.13) plus the live input frame. | 2026-04-27: factory-default mapping confirmed — SI1=NOT, SI2=POT, SI6=SRV-ON, SI8=A-CLR. No HOME sensor is assigned. Useful when planning homing strategies or debugging input-signal behaviour. |
| `move_to_mm.py` | Drive the slider to one or more absolute targets via `LinearMotorController.move_to_mm()` with the closed-loop ±0.1 mm tolerance. | Used for clean origin returns and absolute positioning sanity checks. Edit `targets_mm` (list of mm targets) and `tolerance_mm` between runs. |
| `measure_accuracy.py` | Single-shot accuracy trial for filling in `모터별_정확도_측정.xlsx - Sheet1.csv`. Returns to 0 mm via closed loop, settles, issues one `move_relative_mm` at the chosen speed, and prints the final encoder position. | Edit `target_mm` (10 / 25 / 50 / 100 / 200 mm) and `test_speed` (12 r/min for 25 %, 25 r/min for 50 %) between runs. Includes a 10 s observation countdown and a 60 s motion timeout. |
| `probe_ports.py` | Probe every `/dev/ttyUSB*` port with a MINAS model-name read to locate the RS485 converter after USB re-enumeration. | 2026-06-10: amp answered on `/dev/ttyUSB3`, not the documented `/dev/ttyUSB0` — current converters enumerate as FTDI, and port order changes across replugs. Run this first whenever the smoke test reports "No EOT response". |
| `verify_5mm_motion.py` | End-to-end hardware verification: smoke test, pre-motion parameter check, then `move_to_mm()` +5 mm and back with encoder-delta PASS/FAIL. | See ToDo Task 12. Accepts the port as `argv[1]` (defaults to `/dev/ttyUSB3`). |
| `test_rail_bridge_parse.py` | Offline (no-hardware) test for `rail_bridge.py`: swaps in a fake rail and asserts the `CMD:*` mapping (`MOVE X <mm>` -> `move_to_mm`, `X+/X-` -> step `move_relative_mm`, `X0` -> no-op, `HOME` -> `move_to_mm(0)`) and that out-of-limit / malformed commands are refused. | See ToDo Task 14. Run with the bridge deps installed; exits non-zero on any failed check. |
