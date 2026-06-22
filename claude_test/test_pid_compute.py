"""Offline sanity checks for PIDController.compute() (Issue #9).

Runs with no hardware: drives PIDController with synthetic error
sequences and asserts the P/I/D, output saturation + sign, output_min
floor, deadband, and anti-windup behaviours. Exit code is non-zero if
any check fails.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pid_move_to_mm import PIDController  # noqa: E402

results = []


def check(name, ok):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}")


def near(a, b, eps=1e-9):
    return abs(a - b) <= eps


# P-only (defaults kp=4, ki=kd=0): output = kp * error, well in range.
pid = PIDController()
out, p, i, d = pid.compute(1.0, 0.1)
check(
    "P-only: output = kp*error (4.0)",
    near(out, 4.0) and near(p, 4.0) and near(i, 0.0) and near(d, 0.0),
)

# Saturation: a large error clamps the magnitude to output_max (25).
pid = PIDController()
out, _, _, _ = pid.compute(100.0, 0.1)
check("Saturation: clamps to output_max (25)", near(out, pid.output_max))

# Sign: a negative error yields a negative output of equal magnitude.
pid = PIDController()
out, _, _, _ = pid.compute(-100.0, 0.1)
check("Sign preserved (-25)", near(out, -pid.output_max))

# output_min floor: a tiny non-zero command is raised to output_min.
pid = PIDController()
out, _, _, _ = pid.compute(0.1, 0.1)  # p = 0.4 -> floored to 1
check("output_min floor (1.0)", near(out, 1.0))

# Deadband: an error within deadband_mm produces zero output.
pid = PIDController()
pid.deadband_mm = 0.5
out, _, _, _ = pid.compute(0.3, 0.1)
check("Within deadband -> 0 output", near(out, 0.0))

# Anti-windup: clamped at MAX against a same-sign error freezes the
# integrator.
pid = PIDController(kp=4.0, ki=10.0, kd=0.0)
pid.compute(100.0, 1.0)
check("Anti-windup: integral frozen while saturated", near(pid._integral, 0.0))

# The integrator accumulates when the output is not saturated.
pid = PIDController(kp=0.0, ki=1.0, kd=0.0)
pid.compute(1.0, 1.0)
check("Integral accumulates when unsaturated", near(pid._integral, 1.0))

passed = sum(results)
print(f"\nSUMMARY: {passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
