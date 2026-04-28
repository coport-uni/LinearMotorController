"""Exercise the soft closed-loop absolute-position API move_to_mm.

Drive the slider to several absolute targets and report the
final residual error. Intended for hardware observation of
convergence quality at the default tolerance of 0.1 mm.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from LinearMotorController import LinearMotorController  # noqa: E402


def main():
    """Visit a sequence of absolute targets and print residuals."""
    serial_port = "/dev/ttyUSB0"
    targets_mm = [0.0]
    tolerance_mm = 0.1 # 허용오차

    lmc = LinearMotorController(serial_port)

    start_mm = lmc.read_position_mm()
    print(f"Start position: {start_mm} mm\n")

    all_ok = True
    for target in targets_mm:
        print(f"--- Target {target} mm ---")
        final = lmc.move_to_mm(target, tolerance_mm=tolerance_mm)
        if final is None:
            print(f"FAIL on target {target} mm.")
            all_ok = False
            continue
        residual = final - target
        status = "OK" if abs(residual) <= tolerance_mm else "OUT-OF-SPEC"
        print(f"  Final {final} mm, residual {residual:+.4f} mm [{status}]\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
