"""Verify LinearMotorController on real hardware: move the rail
+5 mm then -5 mm via move_to_mm() and confirm displacement through
the encoder feedback pulse counter."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from LinearMotorController import LinearMotorController  # noqa: E402

SERIAL_PORT = "/dev/ttyUSB3"
TEST_DISTANCE_MM = 5.0
TOLERANCE_MM = 0.1


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else SERIAL_PORT
    lmc = LinearMotorController(port)

    print("=== 1. Smoke test ===")
    model = lmc.read_model_name()
    version = lmc.read_software_version()
    start_mm = lmc.read_position_mm()
    print(f"  Model:    {model}")
    print(f"  Version:  {version}")
    print(f"  Position: {start_mm} mm")
    if model is None or start_mm is None:
        print("FAIL: smoke test did not pass; aborting before motion.")
        return 1

    print("\n=== 2. Pre-motion state ===")
    control_mode = lmc._read_parameter(0, 1)
    speed_setpoint = lmc._read_parameter(3, 4)
    print(f"  Pr0.01 control mode:   {control_mode} (expect 1)")
    print(f"  Pr3.04 internal speed: {speed_setpoint} (expect 0)")
    if control_mode != 1:
        print("FAIL: amp is not in speed control mode; aborting.")
        return 1
    if speed_setpoint not in (0, None) and speed_setpoint != 0:
        print("FAIL: nonzero speed setpoint at rest; aborting.")
        return 1

    print(f"\n=== 3. Move +{TEST_DISTANCE_MM} mm ===")
    forward_target = start_mm + TEST_DISTANCE_MM
    forward_mm = lmc.move_to_mm(forward_target, tolerance_mm=TOLERANCE_MM)
    if forward_mm is None:
        print("FAIL: forward move returned None.")
        return 1
    forward_delta = forward_mm - start_mm
    print(f"  Encoder delta: {forward_delta:+.3f} mm (commanded +5.000)")

    time.sleep(1.0)

    print(f"\n=== 4. Move -{TEST_DISTANCE_MM} mm (back to start) ===")
    back_mm = lmc.move_to_mm(start_mm, tolerance_mm=TOLERANCE_MM)
    if back_mm is None:
        print("FAIL: backward move returned None.")
        return 1
    back_delta = back_mm - forward_mm
    print(f"  Encoder delta: {back_delta:+.3f} mm (commanded -5.000)")

    print("\n=== 5. Summary ===")
    forward_err = forward_mm - forward_target
    return_err = back_mm - start_mm
    print(f"  Start:            {start_mm:+.3f} mm")
    print(f"  After +5 mm move: {forward_mm:+.3f} mm (err {forward_err:+.4f})")
    print(f"  After -5 mm move: {back_mm:+.3f} mm (err {return_err:+.4f})")

    moved_forward = abs(forward_delta - TEST_DISTANCE_MM) <= TOLERANCE_MM
    returned = abs(return_err) <= TOLERANCE_MM
    if moved_forward and returned:
        print("PASS: encoder confirmed +5 mm / -5 mm motion.")
        return 0

    print("FAIL: encoder deltas outside tolerance.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
