"""Single-shot accuracy measurement for the CSV record.

Performs one trial per run:
  1. Returns to origin (0 mm) via the closed-loop move_to_mm to get
     a clean, repeatable starting point.
  2. Waits for residual vibration to settle (per CSV step 5).
  3. Issues one single-speed forward move via move_relative_mm.
  4. Prints the final encoder position so the operator can record
     it after measuring physically with a ruler / caliper.

Edit `target_mm` and `test_speed` between runs to cover the
distance/speed grid (10/25/50/100/200 mm, 12 r/min for 25%, or
25 r/min for 50%).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from LinearMotorController import LinearMotorController  # noqa: E402


def main():
    """Return to home, settle, run a single forward move, report."""
    serial_port = "/dev/ttyUSB0"

    # ----- Edit these between trials -----
    target_mm = 200.0  # 10, 25, 50, 100, 200
    test_speed = 12  # 12 = 25% of default 50, 25 = 50% of default
    settle_seconds = 3.0
    # --------------------------------------

    lmc = LinearMotorController(serial_port)

    print(f"--- Trial: target {target_mm} mm @ speed {test_speed} r/min ---")

    # Count down so the operator can get into observation position.
    startup_wait_s = 10
    print(f"Starting in {startup_wait_s} s — get into position.")
    for remaining in range(startup_wait_s, 0, -1):
        print(f"  {remaining} ...", end="\r", flush=True)
        time.sleep(1)
    print("  start!     ")

    # Origin = the rail position at power-on. Place the rail at one end
    # before running: from the start end use a positive target, from the
    # far end a negative one.
    print("Returning to origin (0 mm) via closed loop ...")
    home_pos = lmc.move_to_mm(0.0)
    if home_pos is None:
        print("FAIL: could not return to origin.")
        return 1
    print(f"  Origin reached: {home_pos:+.4f} mm")

    print(f"Settling for {settle_seconds} s ...")
    time.sleep(settle_seconds)

    pre_move = lmc.read_position_mm()
    print(f"Pre-move position: {pre_move:+.4f} mm")

    print(
        f"Moving +{target_mm} mm relative at {test_speed} r/min"
        f" (single speed, no closed-loop correction) ..."
    )
    # 60 s timeout covers 200 mm at the slowest tested speed (12 r/min)
    # with margin. The default 10 s stops the move early (15 s only
    # reached 157 mm of a 200 mm move).
    final = lmc.move_relative_mm(target_mm, speed=test_speed, timeout=60.0)
    if final is None:
        print("FAIL: move_relative_mm returned None.")
        return 1

    delta = final - pre_move
    print()
    print("=== Result ===")
    print(f"  Final encoder position: {final:+.4f} mm")
    print(f"  Travel from origin:     {delta:+.4f} mm")
    print(f"  Encoder error vs target: {delta - target_mm:+.4f} mm")
    print()
    print("  Now measure physically with a ruler / caliper and record")
    print("  both the encoder reading and the physical reading in the")
    print("  CSV under the appropriate Trial column.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
