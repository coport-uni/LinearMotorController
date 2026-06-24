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

---

## Task 9: Repo-wide MIT Convention Cleanup and Modbus Removal

**Date**: 2026-04-29
**GitHub Issue**: #6

### Purpose

After Tasks 6, 7, and 8 added closed-loop control and a Modbus path,
the repo has accumulated minor MIT Convention drift (shadowed builtin
`self.id`, magic numbers in the serial handshake, inconsistent
variable naming, missing class docstring). At the same time, the
project is committing to MINAS standard protocol only, so all Modbus
artifacts should be removed.

Internal-method `_` prefix naming was audited and is already
consistent, so it is **not** in scope.

### Scope A — `LinearMotorController.py` style cleanup (no behavior change)

- [ ] Add a docstring to the `LinearMotorController` class
- [ ] Rename `self.id` → `self.axis_id` (avoid shadowing builtin `id()`)
- [ ] Move `ENQ/EOT/ACK/NAK` from instance attrs to class-level
      lowercase constants (`_enq/_eot/_ack/_nak`) per CLAUDE.md §1
- [ ] Extract magic numbers to class-level constants
      (`_serial_timeout_s = 2`, `_response_timeout_s = 2`,
      `_no_response_error = 0xFF`)
- [ ] Replace `0x80` literal at L130 with the existing `module_byte`
      computation for consistency with L75
- [ ] Fix " No EOT response from amplifier." leading-space typo (L91)
- [ ] Standardize timing variable name to `start_time`
      (currently mixes `start` and `start_time`)
- [ ] Add explicit parentheses to `(sum(response) & 0xFF) != 0` (L154)

### Scope B — Whole-repo MIT Convention audit

Audit and fix the same class of issues (naming, magic numbers,
docstrings, 80-col, comments) in the rest of the repo:

- [ ] `claude_test/test_connection.py`
- [ ] `claude_test/diagnose_amp_state.py`
- [ ] `claude_test/measure_accuracy.py`
- [ ] `claude_test/move_to_mm.py`
- [ ] `README.md` — verify examples still match the cleaned-up API
      (`axis_id`, removed Modbus class)
- [ ] `claude_test/README.md` — drop rows for any deleted scripts

### Scope C — Remove all Modbus content

The project is committing to MINAS standard protocol only. Remove:

- [ ] Delete `LinearMotorControllerModbus.py`
- [ ] Delete `Modbus_reference.pdf`
- [ ] Delete `MinasA6_driver_main.pdf` (per CLAUDE.md L334 this is
      the Modbus spec PDF; user to confirm before deletion in case
      it is still desired as reference)
- [ ] Delete `claude_test/check_input_signals.py`
      (built specifically for Task 8 stage 1 Modbus feasibility)
- [ ] Edit `CLAUDE.md` Reference Documents section: remove Modbus
      PDF rows (L334, L336)
- [ ] Edit `CLAUDE.md` L7: drop the "not Modbus" parenthetical since
      Modbus is no longer part of the project
- [ ] Mark Task 8 above as cancelled with reason "Modbus path
      dropped; project committed to MINAS standard protocol only."
- [ ] Confirm `LinearMotorController.py` and remaining `claude_test/`
      scripts have no Modbus imports/strings left

### Verification

- [ ] `ruff check` and `ruff format --check` clean across the repo
- [ ] `python3 LinearMotorController.py` runs the same demo on
      hardware (read model / version / position, then move)
- [ ] `git grep -i modbus` returns nothing except historical
      references in this Task 9 / Issue #6
- [ ] Commit and push

---

## Task 10: Sync Repo Conventions and Hooks from CommonClaude

**Date**: 2026-04-28
**Source**: https://github.com/coport-uni/CommonClaude
**GitHub Issue**: #7

### Purpose

Bring the full CommonClaude convention set (CLAUDE.md sections
1–10 plus all enforcement hooks) into this project, while preserving
the project-specific sections (MINAS protocol, hardware setup,
reference PDFs).

### Checklist

- [x] Merge CLAUDE.md: keep project-specific preamble; replace
      convention block with CommonClaude §1–§10
- [x] Update `.claude/settings.json` with env vars and four hook
      event handlers
- [x] Create `.claude/hooks/` with five executable shell scripts
  - [x] `pre-write-guard.sh`
  - [x] `pre-bash-secret-scan.sh`
  - [x] `pre-read-env-guard.sh`
  - [x] `post-write-lint.sh`
  - [x] `post-write-debug-remind.sh`
- [x] Expand `ruff.toml` to full CommonClaude config
- [x] Bootstrap `LearnedPatterns.md` per §10 from Tasks 1–9
- [x] `gh issue create` for this task (#7)
- [ ] Commit and push

---

## Task 11: Re-sync CLAUDE.md with Latest CommonClaude Conventions

**Date**: 2026-06-09
**Source**: https://github.com/coport-uni/CommonClaude (commit e1fa139)

### Purpose

Upstream CommonClaude grew from §1–§10 to §1–§17 since the Task 10
sync. Bring the new sections into this project's CLAUDE.md while
preserving the project-specific preamble (MINAS protocol, hardware
setup) and Python/ruff.toml adaptations (see LP §4 "Convention rules
apply to docs as well as code").

### Checklist

- [x] Merge CLAUDE.md: keep project preamble; adopt upstream §1–§17
  - [x] §4 Task Management: new branch + PR workflow steps
  - [x] §7 Research Before Coding & MCP Servers (Serena, Context7,
        Fetch) — new mandatory-MCP section
  - [x] §11 Commit Messages (Conventional Commits) — new
  - [x] §12 Branching Strategy (GitHub Flow, prefer `gh` CLI) — new
  - [x] §13 .gitignore template — new
  - [x] §14 Versioning (SemVer) — new
  - [x] §15 Pull Request Guidelines — new
  - [x] §16 Git Automation (pre-commit) — new
  - [x] §17 References (Git Convention) — new
  - [x] Keep Python examples in §3/§5 and `ruff.toml` in §6
        (upstream §5 still shows C examples; this is a Python repo)
- [x] Update Reference Documents section to the renamed PDF
      filenames (`MinasA6_driver_main.pdf`, `MinasA6_driver_sub.pdf`,
      `Modbus_reference.pdf`)
- [x] Refresh `CommonCLAUDE.md` snapshot to upstream e1fa139
- [x] `gh issue create` for this task (#12)
- [ ] Commit and push

---

## Task 12: Hardware Verification — ±5 mm Rail Motion Test

**Date**: 2026-06-10

### Purpose

Verify that `LinearMotorController.py` works on the currently
attached hardware by moving the rail forward and backward 5 mm
and confirming actual displacement through the motor encoder
feedback pulse counter.

### Checklist

- [x] Run RS485 smoke test (model, version, position) before any
      motion command (see LP §4)
- [x] Write `claude_test/verify_5mm_motion.py` debug script and
      register it in `claude_test/README.md` (see LP §1)
- [x] Move +5 mm via `move_to_mm()` and confirm encoder delta
      (see LP §2 — never raw `move_relative_mm()` for accuracy)
- [x] Move -5 mm back to start and confirm encoder delta
- [x] Report measured positions and residual errors
- [x] `gh issue create` for this task (#14)
- [x] Commit and push (0e70ca1)

---

## Task 13: Point main() and Docs at the Current Serial Port

**Date**: 2026-06-10

### Purpose

Task 12 found the amp on `/dev/ttyUSB3` after USB re-enumeration
(see LP §5 "`/dev/ttyUSB*` numbering is not stable"). Update the
`main()` demo default and the port mentions in `README.md` and
`CLAUDE.md`, allow a CLI override, then open a PR to `main`.

### Checklist

- [x] `main()`: default port `/dev/ttyUSB3`, accept `argv[1]`
      override (see LP §5)
- [x] Update `README.md` examples to the current port
      (see LP §1 — README and API change in the same task)
- [x] Update `CLAUDE.md` Hardware Setup row (FTDI converter,
      unstable port numbering)
- [x] Ruff check and format (see LP §1)
- [x] Run the demo on hardware and confirm encoder motion
      (see LP §1)
- [x] `gh issue create` for this task (#15)
- [x] Commit, push, and open PR to `main` (6b5e29d, PR #13)

---

## Task 16: WiFi FastAPI rail server (mirror HotplateController)

**Date**: 2026-06-23

### Purpose

Admin redirect: the ESP32 must control the rail over **WiFi (no USB to
the NUC)**, with the **NUC running a FastAPI REST server** on the
dedicated port **17052**. Follow the same form as the sibling repo
`coport-uni/HotplateController` (FastAPI `DeviceMonitor` + ESP32 HTTP
client); only the NUC↔device link differs (RS485/MINAS vs USB-CDC).
`LinearMotorController.py` (+ PID) is unchanged. This task is Phase 1 —
the NUC server.

### Checklist

- [x] `server.py` mirroring `hotplate_controller/server.py`:
      `RailMonitor` (poller thread + lock + atomic snapshot),
      `GET /status` (+`age_seconds`) / `/health` / `/` (HTML dashboard),
      `POST /control/move|jog/start/{dir}|jog/stop|home`, bind
      `0.0.0.0:17052`, `create_app()` + `lifespan` + `main()`
- [x] Reuse the continuous-jog + soft-limit watchdog logic from
      `rail_bridge.py` (lifted into `RailMonitor`); jog has a
      server-side max-duration auto-stop (dropped-`stop` WiFi safety)
- [x] `claude_test/test_server.py` — offline `RailMonitor` logic test
      (snapshot, move limits, jog Pr3.04 writes, disconnected) — 9/9
- [x] `claude_test/poke_server.py` — read-only live probe
- [x] `docs/server_api.md` — endpoints + curl + ESP32 examples
- [x] `requirements.txt` — pyserial + fastapi + uvicorn[standard]
- [x] `ruff check` + `ruff format --check` clean
- [x] Live hardware check on `/dev/ttyUSB4` (supervised, 2026-06-24):
      read-only `/health`/`/status`/`/` OK; control verified end to end
      -- `move{100}` -> 99.973 mm, `jog/start/negative`+`jog/stop`
      -> 49.4 mm, `home` -> -0.099 mm, `move{999}` -> 422
- [x] Commit, push, open PR (5fee311, PR #20)

> Phase 2-4 (the `external/ESP32S3/` ESP-BOX-3 client mirroring
> HotplateController's `external/ESP32S3/`) follow in a separate task.
> `LinearMotorController.py` is the kept RS485 device layer; the
> `rail_bridge.py` serial path (PR #17) is superseded by this server.
