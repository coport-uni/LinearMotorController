"""Read-only diagnostic of Panasonic MINAS A6 amplifier state.

Issue no motion commands. Report control mode, speed setpoint,
drift in the feedback pulse counter, and the raw input-signal
frame so the user can confirm SRV-ON before the next motion test.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from LinearMotorController import LinearMotorController  # noqa: E402


def main():
    """Print amplifier identity, parameters, and encoder drift."""
    serial_port = "/dev/ttyUSB0"

    lmc = LinearMotorController(serial_port)

    print("--- Identity ---")
    print(f"  Model:   {lmc.read_model_name()}")
    print(f"  Version: {lmc.read_software_version()}")

    print("\n--- Parameters ---")
    control_mode = lmc._read_parameter(0, 1)
    print(f"  Pr0.01 control mode:     {control_mode} (expect 1)")
    speed_setpoint = lmc._read_parameter(3, 4)
    print(f"  Pr3.04 internal speed:   {speed_setpoint} (expect 0)")
    pr3_00 = lmc._read_parameter(3, 0)
    print(f"  Pr3.00 speed input sel:  {pr3_00} (expect 1)")

    print("\n--- Feedback drift (no command active) ---")
    first = lmc.read_feedback_pulse_position()
    print(f"  t=0.0 s: position = {first} pulses")
    time.sleep(2.0)
    second = lmc.read_feedback_pulse_position()
    print(f"  t=2.0 s: position = {second} pulses")
    if first is not None and second is not None:
        delta = second - first
        print(f"  Drift:   {delta:+d} pulses over 2.0 s")

    print("\n--- Raw input-signal frame (command=2, mode=7) ---")
    block = lmc._build_command(command=2, mode=7)
    response = lmc._send_and_receive(block)
    if response is None:
        print("  FAIL: no response.")
    else:
        hex_bytes = " ".join(f"{b:02X}" for b in response)
        print(f"  Raw response: {hex_bytes}")
        params, error = lmc._extract_params(response)
        print(f"  Params: {' '.join(f'{b:02X}' for b in params)}")
        print(f"  Error code: 0x{error:02X}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
