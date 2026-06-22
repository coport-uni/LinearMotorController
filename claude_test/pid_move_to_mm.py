"""Iterative PID position controller built on move_relative_mm.

Replace the static [50, 10, 3, 1, 1] r/min speed schedule of
move_to_mm() with a discrete-time PID whose output is the
per-iteration speed command into move_relative_mm. Each tick is
logged to stdout and to a timestamped CSV under claude_test/ for
offline analysis.

Design choice: the PID closes the position loop in software by
iterating speed commands; this honors LearnedPatterns §2 in spirit
even though it does not call move_to_mm() directly. See
ToDo.md Task 11.
"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from LinearMotorController import LinearMotorController  # noqa: E402


class PIDController:
    """Discrete-time PID with anti-windup and EMA-filtered derivative."""

    # Tunables exposed as class attributes per LearnedPatterns §3.
    kp = 4.0
    ki = 0.0
    kd = 0.0
    output_min = 1
    output_max = 25
    deadband_mm = 0.0
    derivative_alpha = 0.2

    def __init__(self, kp=None, ki=None, kd=None):
        if kp is not None:
            self.kp = kp
        if ki is not None:
            self.ki = ki
        if kd is not None:
            self.kd = kd
        self.reset()

    def reset(self):
        """Clear integrator, previous error, and filtered derivative."""
        self._integral = 0.0
        self._prev_error = None
        self._filtered_derivative = 0.0

    def compute(self, error_mm, dt_s):
        """Return signed output in r/min plus the P, I, D terms.

        The output sign tracks the error sign. The caller passes
        abs(output) as the speed argument to move_relative_mm,
        which auto-signs direction from the displacement
        (LinearMotorController.py:358).

        Args:
            error_mm -- target minus current position in mm
            dt_s -- seconds elapsed since the previous compute call

        Return (signed_output_r_per_min, p_term, i_term, d_term).
        """
        p_term = self.kp * error_mm

        if self._prev_error is None:
            raw_d = 0.0
        else:
            raw_d = (error_mm - self._prev_error) / max(dt_s, 1e-3)
        self._filtered_derivative = (
            self.derivative_alpha * raw_d
            + (1.0 - self.derivative_alpha) * self._filtered_derivative
        )
        d_term = self.kd * self._filtered_derivative

        # Conditional anti-windup: skip integration if doing it would
        # push the output further into same-sign saturation.
        unclamped = p_term + self.ki * self._integral + d_term
        same_sign_saturated = (
            unclamped > self.output_max and error_mm > 0
        ) or (unclamped < -self.output_max and error_mm < 0)
        if not same_sign_saturated:
            self._integral += error_mm * dt_s
        i_term = self.ki * self._integral

        output = p_term + i_term + d_term
        sign = 1 if output >= 0 else -1
        magnitude = min(abs(output), float(self.output_max))
        if abs(error_mm) <= self.deadband_mm:
            magnitude = 0.0
        elif magnitude < self.output_min:
            magnitude = float(self.output_min)

        self._prev_error = error_mm
        return sign * magnitude, p_term, i_term, d_term


def main():
    """Drive a sequence of targets via iterative PID and log per tick."""
    serial_port = "/dev/ttyUSB0"
    # Avoid target = 0 mm: it sits on the NOT (negative travel limit)
    # switch, which mechanically absorbs overshoot and masks the real
    # PID convergence behaviour. Use an interior target (100 mm here) so
    # overshoot is measured cleanly, well clear of the 0 mm limit.
    targets_mm = [100.0]
    tolerance_mm = 0.05
    # Set max_iterations = 0 to read residual without moving (no
    # iterations execute; useful as a position-check probe).
    max_iterations = 1
    timeout_per_step = 10.0

    csv_path = Path(__file__).parent / f"pid_log_{int(time.time())}.csv"
    csv_columns = [
        "t",
        "target",
        "pos",
        "err",
        "p",
        "i",
        "d",
        "out",
        "cmd",
    ]

    lmc = LinearMotorController(serial_port)
    # P-only, kp=4.0 (lowered from 8.0). Hardware tuning showed kp=8 with
    # output_max=25 needed 6-8 iterations and could exhaust
    # max_iterations; the linear-regime overshoot ratio 1 + K*kp
    # (K~0.06) predicts kp=4 -> ~1.24x -> ~3-4 iterations to +/-0.05 mm
    # with safer margin. See ToDo.md Task 11.
    pid = PIDController()

    start_mm = lmc.read_position_mm()
    print(f"Start position: {start_mm} mm")
    print(f"CSV log: {csv_path}\n")

    all_ok = True
    try:
        with csv_path.open("w", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(csv_columns)

            for target in targets_mm:
                print(f"--- PID target {target} mm ---")
                pid.reset()
                t_prev = time.time()
                prev_abs_error = None
                converged = False

                for iteration in range(max_iterations):
                    current = lmc.read_position_mm()
                    if current is None:
                        print("  read_position_mm failed.")
                        all_ok = False
                        break
                    error = target - current
                    if abs(error) <= tolerance_mm:
                        print(
                            f"  iter {iteration}: converged at "
                            f"{current:+.4f} mm"
                        )
                        converged = True
                        break

                    t_now = time.time()
                    dt = t_now - t_prev
                    t_prev = t_now
                    out_signed, p, i_term, d = pid.compute(error, dt)
                    cmd = int(round(abs(out_signed)))

                    print(
                        f"  t={t_now:.2f} pos={current:+.4f} "
                        f"err={error:+.4f} P={p:+.2f} "
                        f"I={i_term:+.2f} D={d:+.2f} "
                        f"out={out_signed:+.1f} -> cmd={cmd} r/min"
                    )
                    writer.writerow(
                        [
                            f"{t_now:.3f}",
                            target,
                            current,
                            error,
                            p,
                            i_term,
                            d,
                            out_signed,
                            cmd,
                        ]
                    )
                    fp.flush()

                    if cmd <= 0:
                        print(f"  iter {iteration}: deadband, stop.")
                        converged = True
                        break

                    final = lmc.move_relative_mm(
                        error,
                        speed=cmd,
                        tolerance_mm=tolerance_mm,
                        timeout=timeout_per_step,
                    )
                    if final is None:
                        print("  move_relative_mm failed.")
                        all_ok = False
                        break
                    abs_err = abs(target - final)
                    if prev_abs_error is not None and abs_err >= prev_abs_error:
                        print("  residual stopped decreasing; abort.")
                        break
                    prev_abs_error = abs_err

                final_pos = lmc.read_position_mm()
                if final_pos is None:
                    all_ok = False
                    continue
                residual = final_pos - target
                tag = "OK"
                if abs(residual) > tolerance_mm:
                    tag = "OUT-OF-SPEC"
                print(
                    f"  Final {final_pos} mm, "
                    f"residual {residual:+.4f} mm [{tag}]\n"
                )
                if not converged and abs(residual) > tolerance_mm:
                    all_ok = False
    finally:
        # Defense in depth: move_relative()'s own finally already
        # writes Pr3.04=0 (LinearMotorController.py:381-386). This
        # outer write covers the gap between move_relative_mm calls
        # (e.g. Ctrl+C during read_position_mm).
        try:
            lmc._write_parameter(3, 4, 0)
        except Exception as exc:
            print(f"  outer safety stop failed: {exc}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
