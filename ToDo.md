# ToDo

## Task 1: MIT Code Convention Audit & Remove Unused `move_speed`

**Date**: 2025-04-09
**GitHub Issue**: #1

### Checklist

- [x] Audit `LinearMotorController.py` against MIT Code Convention
  - [x] Docstrings: imperative mood, no signature restatement
  - [x] Naming: snake_case, descriptive verbs for methods
  - [x] Structure: 80-column limit, spacing, alignment
  - [x] Comments: complete sentences, no restating code
- [x] Confirm `move_speed` is unused by other class methods and `main()`
- [x] Remove `move_speed` from `LinearMotorController.py`
- [x] Remove `move_speed` references from `README.md`

---

## Task 2: Add mm-based Movement API & Install Cable Carrier

**Date**: 2025-04-09
**GitHub Issue**: #2

### Checklist

- [x] Set `pulses_per_mm = 1000` (1 um/pulse magnetic encoder)
- [x] Add `move_relative_mm()` and `read_position_mm()` methods
- [x] Update `main()` to use mm-based movement
- [x] Update `README.md` with mm-based API documentation
- [ ] Install cable carrier (케이블캐리어) for cable protection
- [ ] Calibrate `pulses_per_mm` on hardware with ruler measurement
- [x] Create GitHub issue
- [x] Commit and push

---

## Task 5: Linear Rail Connection Test (before mm API hardware test)

**Date**: 2026-04-14
**GitHub Issue**: (pending - gh auth not available in this environment)

### Purpose

Before running the new mm-based API on hardware, verify that the
RS485 link to the Panasonic MINAS A6 amplifier is healthy. A debug
script in `claude_test/` reads model, software version, and current
position as a smoke test.

### Checklist

- [x] Create `claude_test/` directory with index README
- [x] Add `claude_test/test_connection.py`
- [x] Run on hardware (`/dev/ttyUSB0`) and record results
- [x] Update `claude_test/README.md` with findings

---

## Task 6: Ensure Motion Stops on Ctrl+C / Exception

**Date**: 2026-04-14
**GitHub Issue**: (pending - gh auth not available in this environment)

### Problem

In `move_relative()`, the `self._write_parameter(3, 4, 0)` stop
command is inside the `try` block. A KeyboardInterrupt raised during
the feedback polling loop bypasses it; only
`_release_execution_rights()` in `finally` runs. Result: Pr3.04 keeps
the last speed setpoint and the motor continues until it hits
overload or an external stop.

### Fix

Move the stop write into the `finally` block so it runs on every
exit path (normal, exception, Ctrl+C).

### Checklist

- [x] Edit `move_relative()` in `LinearMotorController.py`
- [x] Run `ruff check` / `ruff format --check`
- [x] Verified on hardware with a Ctrl+C during motion (user confirmed)

---

## Task 7: Soft Closed-Loop Position Control (`move_to_mm`)

**Date**: 2026-04-14
**GitHub Issue**: (pending - gh auth not available in this environment)

### Purpose

The existing `move_relative_mm()` uses speed control and overshoots
by 2–7 mm depending on speed — far beyond the ±5 μm hardware spec.
MINAS standard protocol has no direct position command, and
switching to Modbus/Block operation would require rewriting the
entire comms layer. A **software closed-loop** on top of
`move_relative_mm()` reaches ~±0.1 mm with zero protocol changes.

### Approach

Iterate: move remaining error at progressively lower speed
(50 → 10 → 3 → 1 r/min) until within `tolerance_mm`. Abort after
`max_iterations` or if residual error stops decreasing.

### Checklist

- [x] Add `move_to_mm(target_mm, tolerance_mm, max_iterations, ...)` to `LinearMotorController`
- [x] Update `README.md` with the new method
- [x] Add `claude_test/test_move_to_mm.py`
- [x] Update `claude_test/README.md`
- [x] Ruff lint + format
- [x] Verify on hardware at targets 100 / 250 / 50 mm; all converged within ±0.1 mm
- [x] Expose speed schedule as class attribute `move_to_mm_speed_schedule` for discoverability

---

## Task 8: Modbus + Block Operation Homing (Option C)

**Date**: 2026-04-27
**GitHub Issue**: (pending - gh auth not available in this environment)

### Purpose

Provide objective absolute positioning by switching the amp to
Modbus-RTU + Block Operation. Achieves hardware-spec ±5 um repeatability and a
repeatable physical origin via Block Op homing (Command Code 4h).
Existing MINAS standard protocol class is preserved (coexistence
mode); operator picks via Pr5.37 + power cycle.

### Stage 1: Hardware feasibility check (read-only)

- [ ] `claude_test/check_input_signals.py` reads Pr4.00~Pr4.13 +
      command=2/mode=7 frame
- [ ] Run on hardware and decide which limit/HOME signals are wired

### Stage 2: Modbus + Block Op implementation

- [ ] `pip install minimalmodbus`
- [ ] `LinearMotorControllerModbus.py` with home / move_to_mm /
      move_relative_mm / read_position_mm
- [ ] `claude_test/test_modbus_connection.py`
- [ ] `claude_test/test_homing.py`
- [ ] `claude_test/test_modbus_move_to_mm.py`
- [ ] Configure amp via front panel (Pr5.37=2, Pr6.28=1, Pr60.5x)
- [ ] Hardware verify homing + positioning within +/-5 um

### Stage 3: Coexistence

- [ ] README.md "Which class do I use?" table
- [ ] Document Pr5.37 + power-cycle switching procedure
- [ ] Lint everything

---

## Task 3: Fix Remaining MIT Convention Violations

**Date**: 2025-04-09
**GitHub Issue**: #3

### Checklist

- [x] Add module-level docstring
- [x] Remove empty parentheses from class declaration
- [x] Remove redundant comment (`# Mapping mode and command`)
- [x] Extract magic numbers in `main()` to named constants
- [x] Verify motor runs correctly
- [x] Commit and push

---

## Task 4: Add Ruff Linting & Enforce English for Issues/PRs

**Date**: 2025-04-09
**GitHub Issue**: #4

### Checklist

- [x] Create `ruff.toml` with `line-length = 80`
- [x] Apply `ruff format` to `LinearMotorController.py`
- [x] Add linting section (§5) to `CommonCLAUDE.md` and `CLAUDE.md`
- [x] Extend language rule to cover GitHub issues and PRs
- [x] Verify motor runs correctly
- [x] Commit and push
