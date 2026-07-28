# claude_test

Debug, exploratory, and diagnostic scripts. Not part of CI/CD.

Production-quality tests live in `tests/` (if present).

## Index

| File | Purpose | Findings |
|------|---------|----------|
| `test_link_reconnect.py` | Unit tests (no hardware, no serial port) for surviving a USB link that re-enumerates under it: `_open_serial` waiting out an enumeration gap, `_exchange` reopening on `EIO`, and `move_to_mm` refusing to resume across a reconnect. | 2026-07-28: written after the amp was found to couple noise into its own RS485 link, dropping the adapter every few seconds. Two failures, opposite fixes: a read on the stale fd fails forever (reopen is right), while a move that straddles a reconnect ran blind with a speed command latched in the amp (resuming is wrong at any cost — stop, then fail the move). |
| `test_connection.py` | RS485 smoke test: read model, version, and current position from the Panasonic MINAS A6 amplifier over `/dev/ttyUSB0`. | 2026-04-14: PASS — reads MDDLN45SL / Ver.1.016 / position. Use as the first sanity check after any wiring or amp parameter change. |
| `diagnose_amp_state.py` | Read-only diagnostic: identity, Pr0.01 / Pr3.04 / Pr3.00, 2-second feedback drift, and raw input-signal frame. | 2026-04-14: caught a leftover Pr3.04 = -5 after an Err16.0 overload incident, which was the root cause of "amp not moving" symptoms. Run before motion tests and any time the rail behaves unexpectedly. |
| `check_input_signals.py` | Read-only inspection of SI1~SI10 function assignments (Pr4.00~Pr4.13) plus the live input frame. | 2026-04-27: factory-default mapping confirmed — SI1=NOT, SI2=POT, SI6=SRV-ON, SI8=A-CLR. No HOME sensor is assigned. Useful when planning homing strategies or debugging input-signal behaviour. |
| `move_to_mm.py` | Drive the slider to one or more absolute targets via `LinearMotorController.move_to_mm()` with the closed-loop ±0.1 mm tolerance. | Used for clean origin returns and absolute positioning sanity checks. Edit `targets_mm` (list of mm targets) and `tolerance_mm` between runs. |
| `measure_accuracy.py` | Single-shot accuracy trial for filling in `모터별_정확도_측정.xlsx - Sheet1.csv`. Returns to 0 mm via closed loop, settles, issues one `move_relative_mm` at the chosen speed, and prints the final encoder position. | Edit `target_mm` (10 / 25 / 50 / 100 / 200 mm) and `test_speed` (12 r/min for 25 %, 25 r/min for 50 %) between runs. Includes a 10 s observation countdown and a 60 s motion timeout. |
| `probe_ports.py` | Probe every `/dev/ttyUSB*` port with a MINAS model-name read to locate the RS485 converter after USB re-enumeration. | 2026-06-10: amp answered on `/dev/ttyUSB3`, not the documented `/dev/ttyUSB0` — current converters enumerate as FTDI, and port order changes across replugs. Run this first whenever the smoke test reports "No EOT response". |
| `verify_5mm_motion.py` | End-to-end hardware verification: smoke test, pre-motion parameter check, then `move_to_mm()` +5 mm and back with encoder-delta PASS/FAIL. | See ToDo Task 12. Accepts the port as `argv[1]` (defaults to `/dev/ttyUSB3`). |
| `test_server.py` | Offline (no-hardware) test of the FastAPI server's `RailMonitor` logic: connected snapshot shape, `move` within/out-of-limits (`RailRangeError`), `jog_start/stop` Pr3.04 writes, `home`, and the disconnected snapshot. | 2026-06-23: 9/9 PASS. Exercises the logic behind `/status` and `/control/*` without HTTP (the venv lacks httpx for TestClient). Run after editing `server.py`. |
| `poke_server.py` | Read-only probe of a running rail server: GET `/health` + `/status` and print the JSON. Non-actuating. | Confirms the server is up and polling the rail. `python3 claude_test/poke_server.py [BASE_URL]` (default `http://localhost:17052`). |
