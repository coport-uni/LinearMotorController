# MINAS A6 Linear Rail Controller

Python controller for Panasonic MINAS A6 series servo amplifiers driving linear rail systems over RS485 serial communication.

## What This Repo Does

This project provides a Python class (`LinearMotorController`) that communicates with a Panasonic MINAS A6 servo amplifier using the **MINAS standard serial protocol** over RS485. It can:

- Read amplifier model name and software version
- Read the current motor position (feedback pulse counter)
- Move the motor to a relative position with pulse-level monitoring

## Tested Hardware

- **Servo amplifier**: Panasonic MINAS A6 series (tested with MDDLN45SL)
- **RS485 converter**: USB-to-RS485 adapter (tested with TI USB 3410)

## Amplifier Parameter Setup

The amplifier must be configured with the following parameters via the front panel. Parameters marked with `*` require a power cycle to take effect.

| Parameter | Value | Description |
|-----------|-------|-------------|
| `Pr5.37*` | **0** | MINAS standard protocol (factory default) |
| `Pr5.30*` | **2** | RS485 baud rate = 9600 bps (factory default) |
| `Pr5.31*` | **1** | Slave ID / axis number (factory default) |
| `Pr0.01*` | **1** | Speed control mode. **Must be changed from factory default (0).** and Save to EEPROM and cycle power. |
| `Pr3.00`  | **1** | Internal speed input (factory default for some models; verify on yours) |

## Installation

```bash
pip3 install pyserial
```

## Quick Start

```python
from LinearMotorController import LinearMotorController

lmc = LinearMotorController("/dev/ttyUSB0")

# Read amplifier info
print(lmc.read_model_name())           # "MDDLN45SL"
print(lmc.read_software_version())     # "Ver.1.016"
print(lmc.read_feedback_pulse_position())  # current position in pulses

# Move motor +5000 pulses from current position
lmc.move_relative(5000, speed=10)

# Move motor -5000 pulses (reverse)
lmc.move_relative(-5000, speed=10)
```

## API Reference

### `LinearMotorController(port)`

Create a controller instance. Opens the serial port with 9600 bps, 8N1.

```python
lmc = LinearMotorController("/dev/ttyUSB0")
```

### `read_model_name() -> str | None`

Read the 12-character amplifier model name (e.g., `"MDDLN45SL"`).

### `read_software_version() -> str | None`

Read the amplifier software version (e.g., `"Ver.1.016"`).

### `read_feedback_pulse_position() -> int | None`

Read the current motor position as a signed integer in encoder pulse units. The value represents the absolute position from the power-on origin. Positive = forward, negative = reverse.

### `read_input_signals() -> dict | None`

Read the logical input signal states. Return a dict:

```python
{
    "servo_on": True,      # SRV-ON signal active
    "alarm_clear": False,  # Alarm clear input
    "n_ot": True,          # Negative overtravel (True = not triggered)
    "p_ot": True,          # Positive overtravel (True = not triggered)
}
```

### `move_relative(pulse_offset, speed=50, tolerance=500, timeout=10.0) -> int | None`

Move the motor by `pulse_offset` encoder pulses from the current position. Monitor feedback pulses and stop when the target is reached within tolerance.

- `pulse_offset` -- displacement in encoder pulses. Positive = forward, negative = reverse.
- `speed` -- speed in r/min (1~500, direction is set automatically).
- `tolerance` -- acceptable position error in pulses.
- `timeout` -- maximum wait time in seconds.

Returns the final position, or `None` on failure.

> **Note:** This uses speed control mode, not position control. There will be some overshoot after stopping due to deceleration. Lower speed values give better positioning accuracy.

## Communication Protocol

This project uses the **MINAS standard serial protocol** (not Modbus). The protocol uses ENQ/EOT/ACK/NAK handshaking over RS485 half-duplex.

### Handshake Sequence

```
Host (PC)                Amplifier
    |── module_byte+ENQ ──>|   "Request to send"
    |<──────── EOT ────────|   "Ready to receive"
    |── command block ────>|   (data transfer)
    |<──────── ACK ────────|   "Received OK"
    |<──────── ENQ ────────|   "I have response data"
    |── module_byte+EOT ──>|   "Ready to receive"
    |<── response block ───|   (data transfer)
    |──────── ACK ────────>|   "Received OK"
```

### Data Block Structure

```
[N] [axis] [(mode<<4)|command] [params...] [checksum]
```

- `N` -- number of parameter bytes (0~240)
- `axis` -- amplifier axis number (Pr5.31, default 1)
- `(mode<<4)|command` -- command and mode packed into one byte
- `checksum` -- two's complement of the sum of all preceding bytes

### Command Table

| Command | Mode | Description |
|---------|------|-------------|
| 0 | 1 | Read software version |
| 0 | 5 | Read amplifier model (12-char ASCII) |
| 0 | 6 | Read motor model (12-char ASCII) |
| 1 | 7 | Acquire/release execution rights |
| 2 | 0 | Read status |
| 2 | 2 | Read feedback pulse counter (position) |
| 2 | 4 | Read current speed |
| 2 | 7 | Read input signals |
| 7 | 0 | Read parameter |
| 7 | 1 | Write parameter (RAM) |
| 7 | 2 | Write parameter (EEPROM) |

### Parameter write returns error 0xC0

The parameter requires a power cycle to change (e.g., `Pr0.01`). Set it via the front panel, save to EEPROM, and power cycle.

## Reference Documents

Look furthur on uploaded pdf files.

## License

MIT
