"""Smoke-test the RS485 link to the MINAS A6 amplifier."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from LinearMotorController import LinearMotorController  # noqa: E402


def main():
    """Probe amplifier identity and feedback to verify RS485 link."""
    serial_port = "/dev/ttyUSB0"

    print(f"Opening {serial_port} ...")
    lmc = LinearMotorController(serial_port)

    results = {}

    print("Reading model name ...")
    results["model"] = lmc.read_model_name()
    print(f"  -> {results['model']}")

    print("Reading software version ...")
    results["version"] = lmc.read_software_version()
    print(f"  -> {results['version']}")

    print("Reading feedback pulse position ...")
    results["pulses"] = lmc.read_feedback_pulse_position()
    print(f"  -> {results['pulses']}")

    print("Reading position in mm ...")
    results["mm"] = lmc.read_position_mm()
    print(f"  -> {results['mm']}")

    print()
    ok = all(v is not None for v in results.values())
    if ok:
        print("PASS: all reads succeeded.")
        return 0
    print("FAIL: one or more reads returned None.")
    for key, value in results.items():
        if value is None:
            print(f"  - {key}: None")
    return 1


if __name__ == "__main__":
    sys.exit(main())
