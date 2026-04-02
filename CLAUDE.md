# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Panasonic MINAS A6 series servo amplifier controller for linear rail systems. Communicates with the servo amp over RS485 using the **MINAS 표준 프로토콜** (standard serial protocol), not Modbus.

## Hardware Setup

- **RS485 converter**: TI USB 3410 at `/dev/ttyUSB0`
- **Amplifier**: MDDLN45SL (confirmed via RS485 read)
- **Serial settings**: 9600 bps, 8N1 (no parity, 1 stop bit)
- **Amp parameters**: Pr5.37=0 (MINAS standard protocol), Pr5.30=2 (9600bps), Pr5.31=1 (slave ID)

## Running

```bash
pip3 install pyserial
python3 read_version.py
```

## MINAS Standard Protocol Key Details

The protocol uses ENQ/EOT/ACK/NAK handshaking over RS485 half-duplex. Reference: MINAS A6 취급설명서(종합편) P.7-28~7-41.

**Data block structure**: `N | axis | (mode<<4)|command | params[N] | checksum`

- `cmd_mode` byte encoding is `(mode << 4) | command` — **not** the reverse. This was verified empirically against the amp.
- Checksum = 2's complement of the byte sum of all preceding bytes in the block.
- On this RS485 converter (TI USB 3410), the amp responds without the module identification byte prefix — only raw EOT/ENQ/ACK bytes arrive. The code handles this by checking for the control byte directly rather than expecting `module_byte + control_byte` pairs.

**Command table** (command, mode):
- (0, 1): Software version read
- (0, 5): Amp model read (12-char ASCII)
- (0, 6): Motor model read (12-char ASCII)
- (0, A): Amp serial number
- (1, 7): Execution rights acquire/release
- (7, 0-2): Parameter read/write/EEPROM write

## Python Code Style (MIT CommLab CEE)

This project follows the MIT Communication Lab coding and comment style guide.

### Naming
- Variables, functions, constants: `lower_case` (snake_case)
- Classes/types: `CamelCase`
- Modules: `lowercase`
- Names should be descriptive and pronounceable. Length proportional to scope.
- Variables and classes are **nouns**; functions and methods are **verbs**.
- Avoid abbreviations unless self-explanatory. If forced, add a comment defining it.

### Structure
- **80-column limit** per line.
- One statement per line.
- Indent with **4 spaces**, never tabs.
- When breaking long lines, place the operator at the start of the new line.
- Use refactoring-invariant alignment for long argument lists:
  ```python
  result = some_function(
      argument_one,
      argument_two,
      argument_three)
  ```

### Spacing
- One space after comma, none before: `f(x, y, z)`
- One space around `=` (assignment) and comparison operators: `x = 3`, `x < y`
- Arithmetic operators: consistent spacing (`1 + 1` or `1+1`, never `1+ 1`)

### Comments
- Comments are **complete sentences**, used only when naming/structure cannot convey intent.
- Do not restate what the code obviously does.
- TODOs must be specific with owner and technical detail:
  ```python
  # TODO(@name): implement predictor-corrector for stability.
  ```

### Docstrings (PEP 257)
- All modules, public functions, classes, and public methods must have docstrings.
- Use `"""triple double quotes"""`.
- Write as imperative: `"""Return the pathname."""` not `"""Returns the pathname."""`
- Do not restate the function signature in the docstring.
- Multi-line docstrings: summary line, blank line, then details. Closing `"""` on its own line.
  ```python
  def compute_velocity(distance, time):
      """Compute velocity from distance and time.

      Args:
          distance -- travel distance in meters
          time -- elapsed time in seconds

      Return velocity in m/s. Raise ValueError if time is zero.
      """
  ```

## Reference Documents (PDFs in repo)

- `MinasA6_드라이버.pdf` — Modbus통신사양·Block동작기능편 (SX-DSV03384). Register addresses for Modbus mode.
- `MinasA6_드라이버_참고.pdf` — 취급설명서(종합편). Contains MINAS standard protocol spec (P.7-28~7-41), command details, parameter list, wiring diagrams.
- `Modbus_참조.pdf` — Additional Modbus reference.
