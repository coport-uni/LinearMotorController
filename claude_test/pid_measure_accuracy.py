"""Static-speed accuracy characterization (N-trial repeatability).

Repeats N trials of [PID return to home → settle → static-speed
move to target → record residual] and reports per-trial residuals
plus aggregate statistics (mean, std, min, max).

The home phase uses PIDController for a clean repeatable starting
point. The test phase uses a single open-loop `move_relative_mm()`
call at a fixed speed — this measures the raw overshoot of
move_relative_mm at that speed (the LP §2 plant behaviour), NOT
PID closed-loop convergence.

Edit `target_mm`, `home_mm`, `num_trials`, `test_speed` between
sessions.
"""

import csv
import math
import sys
import time
from pathlib import Path

# Add this dir for pid_move_to_mm, and the parent for
# LinearMotorController.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pid_move_to_mm import PIDController  # noqa: E402

from LinearMotorController import LinearMotorController  # noqa: E402


def pid_drive(
    lmc,
    pid,
    target_mm,
    tolerance_mm,
    max_iterations,
    timeout_per_step,
):
    """Drive slider to target_mm via iterative PID. Return final position
    or None on hardware failure.
    """
    pid.reset()
    t_prev = time.time()
    prev_abs_error = None
    for _iteration in range(max_iterations):
        current = lmc.read_position_mm()
        if current is None:
            return None
        error = target_mm - current
        if abs(error) <= tolerance_mm:
            return current
        t_now = time.time()
        dt = t_now - t_prev
        t_prev = t_now
        out_signed, _, _, _ = pid.compute(error, dt)
        cmd = int(round(abs(out_signed)))
        if cmd <= 0:
            return current
        final = lmc.move_relative_mm(
            error,
            speed=cmd,
            tolerance_mm=tolerance_mm,
            timeout=timeout_per_step,
        )
        if final is None:
            return None
        abs_err = abs(target_mm - final)
        if prev_abs_error is not None and abs_err >= prev_abs_error:
            break
        prev_abs_error = abs_err
    return lmc.read_position_mm()


def main():
    """Run N static-speed accuracy trials and report statistics."""
    serial_port = "/dev/ttyUSB0"
    target_mm = 100.0  # measurement target distance
    home_mm = 30.0  # safe interior point for trial start
    num_trials = 5
    test_speed = 25  # static r/min for the test move
    test_timeout = 60.0  # seconds; matches measure_accuracy.py pattern
    home_tolerance_mm = 0.05  # only governs PID home convergence
    max_iterations = 2  # iterations per home (user-tuned for speed)
    home_timeout_per_step = 10.0
    countdown_s = 10
    settle_s = 3.0

    csv_path = Path(__file__).parent / f"pid_accuracy_{int(time.time())}.csv"
    csv_columns = ["trial", "pre_pos", "final_pos", "residual_mm"]

    lmc = LinearMotorController(serial_port)
    pid_home = PIDController(kp=4.0, ki=0.0, kd=0.0)

    print("=== Static-speed accuracy characterization ===")
    print(
        f"Target: {target_mm} mm, Home: {home_mm} mm, "
        f"Trials: {num_trials}, Test speed: {test_speed} r/min"
    )
    print(f"CSV: {csv_path}\n")

    print(f"Starting in {countdown_s} s — get into observation position.")
    for remaining in range(countdown_s, 0, -1):
        print(f"  {remaining} ...", end="\r", flush=True)
        time.sleep(1)
    print("  start!     \n")

    residuals = []
    run_completed = False
    try:
        with csv_path.open("w", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(csv_columns)

            for trial in range(1, num_trials + 1):
                print(f"--- Trial {trial}/{num_trials} ---")

                print(f"  Returning to home {home_mm} mm via PID...")
                home_final = pid_drive(
                    lmc,
                    pid_home,
                    home_mm,
                    home_tolerance_mm,
                    max_iterations,
                    home_timeout_per_step,
                )
                if home_final is None:
                    print("  FAIL: home return failed.")
                    break
                print(f"  Home position: {home_final:+.4f} mm")

                time.sleep(settle_s)

                pre_pos = lmc.read_position_mm()
                if pre_pos is None:
                    print("  FAIL: pre-move read failed.")
                    break
                print(f"  Pre-move: {pre_pos:+.4f} mm")

                relative_mm = target_mm - pre_pos
                print(
                    f"  Static move {relative_mm:+.4f} mm "
                    f"@ {test_speed} r/min..."
                )
                final_pos = lmc.move_relative_mm(
                    relative_mm,
                    speed=test_speed,
                    timeout=test_timeout,
                )
                if final_pos is None:
                    print("  FAIL: static move failed.")
                    break

                residual = final_pos - target_mm
                residuals.append(residual)
                print(
                    f"  Final {final_pos:+.4f} mm, "
                    f"residual {residual:+.4f} mm\n"
                )
                writer.writerow([trial, pre_pos, final_pos, residual])
                fp.flush()
            else:
                run_completed = True
    finally:
        try:
            lmc._write_parameter(3, 4, 0)
        except Exception as exc:
            print(f"  outer safety stop failed: {exc}")

    if residuals:
        n = len(residuals)
        mean = sum(residuals) / n
        var = sum((r - mean) ** 2 for r in residuals) / n
        std = math.sqrt(var)
        max_abs = max(abs(r) for r in residuals)
        min_signed = min(residuals)
        max_signed = max(residuals)
        print("=== Aggregate Statistics ===")
        print(f"  N = {n}, Target = {target_mm} mm")
        print(f"  Mean residual: {mean:+.4f} mm")
        print(f"  Std deviation: {std:.4f} mm")
        print(f"  Min residual:  {min_signed:+.4f} mm")
        print(f"  Max residual:  {max_signed:+.4f} mm")
        print(f"  Max |residual|: {max_abs:.4f} mm")

    return 0 if run_completed else 1


if __name__ == "__main__":
    sys.exit(main())
