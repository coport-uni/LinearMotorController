# LearnedPatterns.md

> Patterns extracted from completed `[x]` items in `ToDo.md`.
> Format per `CLAUDE.md §10 Learned Patterns Bootstrap`.
> Bootstrapped on 2026-04-28 from Tasks 1–9 (Task 10 is the bootstrap itself).
> Source ToDo entries cited as `(from ToDo#N)`.

---

## §1. Recurring Issues

### Lint must be re-run after every Python edit
- **Problem**: Ruff violations slipped into commits when lint was run only at task end.
- **Cause**: Edits accumulated between lint passes, so a violation introduced mid-task could ride along into the commit before being caught.
- **Fix**: Run `ruff check <file>.py` and `ruff format --check <file>.py` immediately after each Python write.
- **Rule**: Always re-run ruff after every `.py` edit, not only before commit.
(from ToDo#3, #4, #6, #7)

### Hardware verification is required before marking a motion-API change complete
- **Problem**: Code that compiles and lints clean can still misbehave on the actual rail (overshoot, wrong direction, no stop on interrupt).
- **Cause**: The MINAS amp + encoder + mechanical loop is the only authority on whether positioning is correct; static analysis cannot confirm it.
- **Fix**: After every change to `LinearMotorController.py` or `LinearMotorControllerModbus.py`, run the demo on `/dev/ttyUSB0` and observe the rail.
- **Rule**: Always verify motor behavior on hardware before checking off a motion-related ToDo item.
(from ToDo#3, #6, #7)

### README and API must change in the same task
- **Problem**: API additions or removals (`move_speed` removal, `move_relative_mm`, `move_to_mm`) drifted out of sync with `README.md` when the doc update was deferred.
- **Cause**: Doc updates are easy to defer because they don't affect runtime; the code change feels "done" once the test passes.
- **Fix**: Treat the README edit as part of the same checklist as the API edit, not a follow-up.
- **Rule**: Always update `README.md` in the same task that adds, removes, or renames a public method.
(from ToDo#1, #2, #7)

### `claude_test/README.md` must be updated whenever a file is added to `claude_test/`
- **Problem**: New debug scripts landed in `claude_test/` without an index entry, so future readers had to grep to learn what each file did.
- **Cause**: `claude_test/README.md` is a hand-maintained index, not auto-generated.
- **Fix**: When adding `claude_test/<name>.py`, add a row to the README table in the same edit.
- **Rule**: Always update `claude_test/README.md` whenever a new file is added under `claude_test/`.
(from ToDo#5, #7)

---

## §2. Solved Gotchas

### KeyboardInterrupt bypassed the motor stop write
- **Problem**: Pressing Ctrl+C during the feedback polling loop in `move_relative()` left the motor running until external overload or stop.
- **Cause**: The `_write_parameter(3, 4, 0)` stop command was inside the `try` block; only `_release_execution_rights()` in `finally` ran on interrupt, so Pr3.04 retained the last speed setpoint.
- **Fix**: Move the stop write into the `finally` block so it runs on every exit path (normal, exception, Ctrl+C).
- **Rule**: Always place safety-critical hardware-stop writes in `finally`, never in `try`.
(from ToDo#6)

### Speed-control move overshoots the ±5 μm hardware spec
- **Problem**: `move_relative_mm()` overshoots target by 2–7 mm depending on speed — far beyond the rail's ±5 μm spec.
- **Cause**: MINAS standard protocol exposes only speed control (Pr3.04), not direct position command; deceleration profile alone cannot hit a precise target.
- **Fix**: `move_to_mm()` iterates: it moves the residual error at progressively lower speeds (50 → 10 → 3 → 1 r/min) until within `tolerance_mm`. Reaches ~±0.1 mm with no protocol changes.
- **Rule**: Never use raw `move_relative_mm()` for accuracy work; always go through `move_to_mm()` for closed-loop targeting.
(from ToDo#7)

### Magic numbers in `main()` obscured intent
- **Problem**: `main()` contained bare numeric literals for speeds, positions, and timeouts, making the demo hard to read and tune.
- **Cause**: Numbers were inlined during prototyping and never extracted.
- **Fix**: Pull each number into a named constant at module or function scope before committing.
- **Rule**: Always extract numeric literals in `main()` or other entry points to named constants once the demo stabilizes.
(from ToDo#3)

### Empty class parentheses and stray comments lingered after refactor
- **Problem**: `class LinearMotorController():` (empty parens) and a `# Mapping mode and command` comment that restated code remained after a refactor.
- **Cause**: Mechanical edits (renaming, extracting) leave behind syntactic noise that doesn't break anything but violates §2 Comments / §2 Structure.
- **Fix**: Remove empty parentheses on bare classes and delete comments that only restate the next line.
- **Rule**: Always sweep for empty parens and code-restating comments after a refactor pass.
(from ToDo#3)

---

## §3. Library Quirks

### `move_to_mm_speed_schedule` exposed as class attribute for discoverability
- **Problem**: The closed-loop speed schedule was buried inside the `move_to_mm()` body, so callers could not see or override the convergence profile.
- **Cause**: Initial implementation hid the schedule as a local literal list.
- **Fix**: Promote the schedule to a class attribute `move_to_mm_speed_schedule` so it shows up in introspection and can be tuned per instance.
- **Rule**: Always expose tunable algorithm parameters as class attributes, not as in-method literals.
(from ToDo#7)

---

## §4. Workflow Lessons

### Smoke-test the serial link before running a new motion API on hardware
- **Problem**: New mm-based methods could fail for two unrelated reasons — comms-layer breakage or motion-logic bug — and distinguishing them after the fact was slow.
- **Cause**: Without a connection-only check, every motion-test failure forces re-debugging of the serial layer too.
- **Fix**: Run a `claude_test/test_connection.py` smoke test (model, software version, current position) on `/dev/ttyUSB0` before invoking any motion command.
- **Rule**: Always run the RS485 smoke test before the first hardware run of a new motion API change.
(from ToDo#5)

### Audit usage before removing an API surface
- **Problem**: Removing a public method (`move_speed`) without confirming non-use risks breaking external callers.
- **Cause**: Class methods can be called from `main()`, other class methods, or external scripts, and the search is easy to skip.
- **Fix**: Grep `move_speed` across the class methods and `main()` before deleting; only then remove and update `README.md`.
- **Rule**: Always audit usage across the class and entry points before removing a public method.
(from ToDo#1)

### Convention rules apply to docs as well as code
- **Problem**: Korean strings appeared in commit messages, GitHub issues, and PRs even though code comments were English.
- **Cause**: The original §2 Language rule named only code comments and docstrings.
- **Fix**: Extend the rule explicitly to GitHub issues and PRs in `CLAUDE.md` §2 Language.
- **Rule**: Always keep all Claude-authored text — code, docs, commits, issues, PRs — in English.
(from ToDo#4)

---

## §5. Environment Specifics

### Magnetic encoder is 1 μm/pulse → `pulses_per_mm = 1000`
- **Problem**: Without a fixed pulses-per-mm constant, every mm-based call had to recompute the conversion ad hoc.
- **Cause**: The MINAS A6 + this rail's magnetic encoder yields exactly 1000 pulses per millimeter (1 μm per pulse).
- **Fix**: Set `pulses_per_mm = 1000` once, derive `move_relative_mm()` and `read_position_mm()` from it.
- **Rule**: Always reuse `pulses_per_mm` for unit conversion; never inline `* 1000` or `/ 1000`.
(from ToDo#2)

### `/dev/ttyUSB*` numbering is not stable across USB re-enumeration
- **Problem**: The smoke test failed with "No EOT response" on the documented `/dev/ttyUSB0` even though the amp was powered and wired.
- **Cause**: USB replug/re-enumeration reordered the serial ports; the RS485 converter (now enumerating as FTDI, with several other FTDI devices present) landed on `/dev/ttyUSB3`.
- **Fix**: `claude_test/probe_ports.py` probes every `/dev/ttyUSB*` with a MINAS model-name read and reports which port answers.
- **Rule**: Always run `probe_ports.py` to locate the amp when the smoke test reports "No EOT response"; never assume `/dev/ttyUSB0`.
(from ToDo#12)

### Cable carrier and `pulses_per_mm` calibration are still pending hardware tasks
- **Problem**: Two ToDo#2 items — installing the cable carrier (케이블캐리어) and calibrating `pulses_per_mm` against a ruler — remain unchecked.
- **Cause**: Both require physical access to the rail and were deferred when prior tasks took priority.
- **Fix**: Track them under ToDo#2's open boxes; do not lose them in the larger backlog.
- **Rule**: Always re-surface ToDo#2's two open hardware items when next on-site at the rail.
(from ToDo#2)

---

## §99. Uncategorized

*(empty — every completed `[x]` item from Tasks 1–9 fits one of §1–§5.)*
