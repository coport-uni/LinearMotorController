# MINAS A6 Linear Rail Controller

Python controller for Panasonic MINAS A6 series servo amplifiers driving linear rail systems over RS485 serial communication.

## What This Repo Does

This project provides a Python class (`LinearMotorController`) that communicates with a Panasonic MINAS A6 servo amplifier using the **MINAS standard serial protocol** over RS485. It can:

- Read amplifier model name and software version
- Read the current motor position (encoder pulses or mm)
- Move the motor in millimeters, both relative and absolute, with software closed-loop reaching ±0.1 mm precision

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
| `Pr0.01*` | **1** | Speed control mode. **Must be changed from factory default (0).** Save to EEPROM and cycle power. |
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
print(lmc.read_position_mm())              # current position in mm

# Move motor +40 mm from current position
lmc.move_relative_mm(40.0, speed=100)

# Move motor -40 mm (reverse)
lmc.move_relative_mm(-40.0, speed=100)
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

### `read_position_mm() -> float | None`

Read the current motor position in millimeters. Convert feedback pulses using `pulses_per_mm` (default 1000, based on 1 um magnetic encoder resolution).

### `move_relative_mm(distance_mm, speed=50, tolerance_mm=0.5, timeout=10.0) -> float | None`

Move the motor by `distance_mm` millimeters from the current position. Convert mm to pulses internally and delegate to `move_relative()`.

- `distance_mm` -- displacement in millimeters. Positive = forward, negative = reverse.
- `speed` -- speed in r/min (1~500, direction is set automatically).
- `tolerance_mm` -- acceptable position error in mm (default 0.5 mm).
- `timeout` -- maximum wait time in seconds.

Returns the final position in mm, or `None` on failure.

### `move_to_mm(target_mm, tolerance_mm=0.1, max_iterations=5, timeout_per_step=10.0) -> float | None`

Move to an **absolute target position** in millimeters using a software closed loop. Internally iterates `move_relative_mm()` with a descending speed schedule (50 → 10 → 3 → 1 r/min) so that speed-mode overshoot collapses into `tolerance_mm` (default ±0.1 mm).

- `target_mm` -- absolute target position in mm (from power-on origin).
- `tolerance_mm` -- acceptable position error in mm.
- `max_iterations` -- correction attempts cap (default 5).
- `timeout_per_step` -- per-move timeout in seconds.

Returns the final position in mm, or `None` on failure. Returns early without motion if already within tolerance. Aborts if the residual error stops decreasing (convergence stalled).

**Tuning speeds:** The iteration speeds are taken from the class attribute `move_to_mm_speed_schedule` (default `[50, 10, 3, 1, 1]` r/min). Edit this one list at the top of the class to change `move_to_mm` speeds project-wide; the first entry is the coarse approach speed and later entries shrink overshoot.

### `move_relative(pulse_offset, speed=50, tolerance=500, timeout=10.0) -> int | None`

Move the motor by `pulse_offset` encoder pulses from the current position. Monitor feedback pulses and stop when the target is reached within tolerance.

- `pulse_offset` -- displacement in encoder pulses. Positive = forward, negative = reverse.
- `speed` -- speed in r/min (1~500, direction is set automatically).
- `tolerance` -- acceptable position error in pulses.
- `timeout` -- maximum wait time in seconds.

Returns the final position, or `None` on failure.

> **Note:** This uses speed control mode, not position control. There will be some overshoot after stopping due to deceleration. Lower speed values give better positioning accuracy.

### Calibration

The default `pulses_per_mm = 1000` assumes a 1 um/pulse magnetic linear encoder (Misumi E-RAM17-S). To calibrate on your hardware:

1. Move a known number of pulses with `move_relative()`
2. Measure the actual distance with a ruler
3. Set `LinearMotorController.pulses_per_mm = pulse_delta / measured_mm`

## Communication Protocol

This project uses the **MINAS standard serial protocol**. The protocol uses ENQ/EOT/ACK/NAK handshaking over RS485 half-duplex.

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
