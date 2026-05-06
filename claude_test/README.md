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
| `pid_move_to_mm.py` | PID-controlled absolute positioning. Replaces the static `[50, 10, 3, 1, 1] r/min` schedule of `move_to_mm()` with a discrete-time PID whose output is the per-iteration speed command into `move_relative_mm()`. Tunable gains, anti-windup, EMA-filtered derivative; per-tick stdout plus CSV log under `claude_test/pid_log_<unix_ts>.csv`. | 2026-05-06: tuned to `kp=4.0, ki=0.0, kd=0.0, output_max=25 r/min, tolerance_mm=0.05`. P-only is sufficient — D is useless at ~3 s tick rate, I unneeded since residuals are noise-floor bound. Repeatability over 5 trials × 3 targets (`[100, 50, 30] mm`): 15/15 within ±0.05 mm, worst residual 0.042 mm. Per-target mean residual 100mm:−0.009, 50mm:+0.028, 30mm:+0.026; std 0.009–0.016 mm. Convergence 4–5 iter per target. Two empirical findings forced changes from the original spec: (a) `move_relative_mm` overshoots commanded distance by ~1.6× regardless of speed, so `output_max` was lowered from 500 to 25 r/min — first-iter overshoot dropped from 37 mm to 1.7 mm; (b) target = 0 mm hits the SI1=NOT travel limit, mechanically masking PID dynamics, so it was replaced with target = 30 mm. |
