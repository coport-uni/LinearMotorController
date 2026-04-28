"""Inspect MINAS A6 X4 input-signal assignments and live states.

Read-only diagnostic. Reads the SI1~SI10 function-assignment
parameters (Pr4.00~Pr4.13) plus the live input frame
(command=2, mode=7) and prints what is assigned where, with current
state. The output guides whether POT/NOT/HOME signals are usable
for Block Operation homing in Stage 2.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from LinearMotorController import LinearMotorController  # noqa: E402

# Best-effort decode table for low-byte function codes. Codes not
# in this map are printed as raw hex; cross-check P.4-38~40 of
# the MinasA6 manual.
KNOWN_FUNCTION_CODES = {
    0x00: "—  (unassigned)",
    0x01: "POT (positive over-travel inhibit)",
    0x02: "NOT (negative over-travel inhibit)",
    0x03: "SRV-ON",
    0x04: "A-CLR (alarm clear)",
    0x05: "C-MODE (control mode switch)",
    0x06: "GAIN (gain switch)",
    0x07: "INH (pulse inhibit)",
    0x08: "CL  (counter clear)",
    0x09: "INTSPD1",
    0x0A: "INTSPD2",
    0x0B: "INTSPD3",
    0x0E: "ZEROSPD",
    0x14: "HOME (origin sensor)",
    0x16: "E-STOP",
    0x22: "STB (Block Op strobe)",
}

# Pr4.00 -> SI1 ... Pr4.13 -> SI10. Wiring per MINAS A6 X4 connector.
SI_PARAMS = [
    (0, "Pr4.00", "SI1", 8),
    (1, "Pr4.01", "SI2", 9),
    (2, "Pr4.02", "SI3", 26),
    (3, "Pr4.03", "SI4", 27),
    (4, "Pr4.04", "SI5", 28),
    (5, "Pr4.05", "SI6", 29),
    (6, "Pr4.06", "SI7", 30),
    (7, "Pr4.07", "SI8", 31),
    (10, "Pr4.10", "SI9", None),
    (13, "Pr4.13", "SI10", None),
]


def decode_function(byte_value):
    """Return a human label for a single 8-bit function code.

    Bit 7 (0x80) flags a b-contact (inverted) assignment.
    """
    if byte_value == 0:
        return "—"
    is_b_contact = bool(byte_value & 0x80)
    code = byte_value & 0x7F
    label = KNOWN_FUNCTION_CODES.get(
        code,
        f"unknown(0x{code:02X})",
    )
    contact = "b-contact" if is_b_contact else "a-contact"
    return f"{label} [{contact}]"


def main():
    """Print SI assignments and live input bits for the amp."""
    serial_port = "/dev/ttyUSB0"

    lmc = LinearMotorController(serial_port)

    print("--- SI input assignments (Pr4.xx) ---")
    print("Each parameter packs three bytes: P-mode | S-mode | T-mode.")
    print()
    print(
        f"{'Param':7} {'SI':4} {'Pin':4} {'Raw':>10}  P-mode / S-mode / T-mode"
    )
    print("-" * 78)
    for number, name, si, pin in SI_PARAMS:
        value = lmc._read_parameter(4, number)
        if value is None:
            print(f"{name:7} {si:4} {str(pin or '?'):4}      None  read error")
            continue
        raw = value & 0x00FFFFFF
        p_byte = (raw >> 16) & 0xFF
        s_byte = (raw >> 8) & 0xFF
        t_byte = raw & 0xFF
        pin_str = str(pin) if pin is not None else "?"
        print(f"{name:7} {si:4} {pin_str:4}  0x{raw:06X}")
        print(f"  P: {decode_function(p_byte)}")
        print(f"  S: {decode_function(s_byte)}")
        print(f"  T: {decode_function(t_byte)}")

    print("\n--- Live input frame (command=2, mode=7) ---")
    block = lmc._build_command(command=2, mode=7)
    response = lmc._send_and_receive(block)
    if response is None:
        print("  FAIL: no response.")
        return 1

    params, error = lmc._extract_params(response)
    print(f"  Raw bytes: {' '.join(f'{b:02X}' for b in response)}")
    print(f"  Params:    {' '.join(f'{b:02X}' for b in params)}")
    print(f"  Error:     0x{error:02X}")

    if len(params) >= 1:
        physical = params[0]
        print(
            f"\n  Physical input bitmap byte 0 = 0x{physical:02X}"
            f" = 0b{physical:08b}"
        )
        print("  Bit -> SI line state (1 = input ON):")
        for bit in range(8):
            si_index = bit + 1
            state = (physical >> bit) & 1
            print(f"    bit {bit} -> SI{si_index}: {state}")

    print(
        "\nCross-reference the function codes against the MinasA6"
        "\nmanual P.4-38~40 if any 'unknown' codes appear above."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
