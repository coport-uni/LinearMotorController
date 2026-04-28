# claude_test

Debug, exploratory, and throwaway test scripts. Not part of CI/CD.

Production-quality tests live in `tests/` (if present).

## Index

| File | Purpose | Findings |
|------|---------|----------|
| `test_connection.py` | RS485 smoke test: read model, version, and current position from the Panasonic MINAS A6 amplifier over `/dev/ttyUSB0` | 2026-04-14: PASS after powering on the multi-tap. Reads MDDLN45SL / Ver.1.016 / 584 pulses / 0.584 mm. Initial failure was caused by amp power being off ("No EOT response" on all reads). |
| `test_move_50mm.py` | Command a single +50 mm relative move via `move_relative_mm()` at speed 100 | 2026-04-14: moved 0.585 mm -> 57.448 mm (delta 56.863 mm, **+6.9 mm overshoot / 13.7 %** at speed 100). Confirms hardware motion and pulse-to-mm mapping. |
| `test_return_to_origin.py` | Read current mm and issue `move_relative_mm(-current)` at speed 50 to return near origin | 2026-04-14: from 57.463 mm -> -2.438 mm (**overshoot 2.4 mm past 0**). Halving speed from 100 to 50 cut overshoot from 6.9 mm to 2.4 mm. |
| `test_move_to_plus_end.py` | Move toward +end at speed 1 r/min (min) with 900 s timeout, for visual observation | 2026-04-14: started at -2.438 mm; user observed motion and interrupted. Post-interrupt position 302.831 mm — travel ~305 mm confirmed real. |
| `test_move_minus_1m.py` | Move -1000 mm at speed 5 r/min with 900 s timeout | 2026-04-14: script created; user rejected execution. No run-time result. |
| `diagnose_amp_state.py` | Read-only diagnostic: ID, Pr0.01/Pr3.04/Pr3.00, feedback drift, raw input-signal frame | 2026-04-14: Model MDDLN45SL Ver.1.016. Pr0.01=1 (OK), **Pr3.04=-5 (stale, expected 0)**, Pr3.00=1 (OK). Drift -1 pulse/2s (no real motion). Input frame `05 01 72 2D 00 00 78 00 E3` (error 0x00). Conclusion: amp has leftover -5 speed command but is not producing torque — suspect latched alarm or SRV-ON dropped. Root cause was Err16.0 overload from hitting end-stop. Resolved after power cycle + manual slider repositioning. |
| `test_move_to_mm.py` | Visit 100 / 250 / 50 mm absolute targets using the soft closed-loop `move_to_mm` with ±0.1 mm tolerance | 2026-04-14: PASS on all 3 targets. 100 mm → residual +0.099 mm (3 iters); 250 mm → -0.053 mm (4 iters); 50 mm → +0.054 mm (4 iters). Per-iter error shrinks ~4x. Closed-loop successfully hits ±0.1 mm target precision despite speed-mode overshoot. |
| `check_input_signals.py` | Stage 1 of Modbus/Block Op project: read SI1~SI10 function assignments (Pr4.00~Pr4.13) and the live input frame to determine which limit/HOME signals are wired | 2026-04-27: factory-default assignments. SI1=NOT (pin 8, b-contact), SI2=POT (pin 9, b-contact), SI6=SRV-ON (pin 29), SI8=A-CLR (pin 31). **No HOME sensor (0x14) is assigned anywhere.** Live frame `05 01 72 2D 00 00 78 00 E3`. Stage 2 must use limit-based homing or virtual-HOME-coil approach; physical wiring of POT/NOT limits still to be confirmed by manually pushing slider to ends and re-running. |
| `test_modbus_connection.py` | Stage 2: smoke-test Modbus-RTU link via LinearMotorControllerModbus. Reads error code, position, BUSY/HOME-CMP/COIN coils | _pending: requires Pr5.37=2 + power cycle first_ |
| `test_homing.py` | Stage 2: alarm clear, SRV-ON, run Block 0 homing (CC=4h), report final position and error code | _pending: requires Modbus mode + amp setup_ |
| `test_modbus_move_to_mm.py` | Stage 2: absolute positioning via Block Op CC=2h to 50/200/100 mm targets, report residuals in um | _pending: requires successful homing first_ |
| `measure_accuracy.py` | Single-shot accuracy trial for the CSV record. Returns to 0 mm via closed loop, settles, issues one `move_relative_mm` at fixed speed, prints final position. Edit `target_mm` and `test_speed` between runs. | running by user |
