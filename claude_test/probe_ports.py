"""Probe every /dev/ttyUSB* port for a MINAS amp responding to the
standard protocol, to locate the RS485 converter after USB re-enumeration."""

import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from LinearMotorController import LinearMotorController  # noqa: E402


def main():
    ports = sorted(glob.glob("/dev/ttyUSB*"))
    print(f"Candidate ports: {ports}")

    found = None
    for port in ports:
        print(f"\n--- Probing {port} ---")
        try:
            lmc = LinearMotorController(port)
            # Shorten the timeout so a dead port fails fast.
            lmc.ser.timeout = 0.5
            model = lmc.read_model_name()
            lmc.ser.close()
        except Exception as exc:
            print(f"  open/read failed: {exc}")
            continue

        print(f"  model: {model}")
        if model:
            found = port

    print(
        f"\nRESULT: amp found on {found}"
        if found
        else "\nRESULT: no amp found on any port"
    )


if __name__ == "__main__":
    main()
