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

---

## Task 17: ESP-BOX-3 WiFi client (external/ESP32S3, mirror HotplateController)

**Date**: 2026-06-23

### Purpose

Phase 2-4 of the WiFi redesign: a new `external/ESP32S3/` ESP-IDF
firmware for the ESP32-S3-BOX-3 that controls the rail over WiFi via the
FastAPI server (Task 16, `:17052`), with **no USB link to the NUC**.
Mirrors HotplateController's `external/ESP32S3/` exactly (WiFi STA + a
command-queue + single HTTP client task + LVGL UI); only the device and
the commands differ (rail jog/home vs hotplate temp/speed/heater/motor).

### Checklist

- [x] Build files: `CMakeLists.txt`, `sdkconfig.defaults`,
      `main/CMakeLists.txt`, `main/idf_component.yml` (esp-box-3 + cjson),
      `main/Kconfig.projbuild` (`RAIL_WIFI_*` / `RAIL_SERVER_URL` (default
      `:17052`) / `RAIL_POLL_INTERVAL_S`)
- [x] `main/network.c/.h` — WiFi STA (copied from hotplate, `RAIL_*`)
- [x] `main/rail_client.c/.h` — mirror `hotplate_client.c`: command queue
      + single task, `make_url`/`http_get`/`http_post`, cJSON parse,
      `fetch_status` (GET /status -> `ui_set_status`), `execute_command`
      (POST /control/jog/start/{dir}, /control/jog/stop, /control/home)
- [x] `main/ui.c/.h` — LVGL readings panel (position / target / state /
      age) + **hold-to-jog** buttons (PRESSED -> jog/start, RELEASED ->
      jog/stop) + a Home button
- [x] `main/buttons_check.c/.h` + `main/main.c` — on-board CONFIG button
      homes the rail; init order network_init -> rail_client_init
- [x] `external/ESP32S3/README.md` + `.gitignore` (build/ etc.)
- [x] `idf.py build` clean (ESP-IDF v6.0.1, zero warnings) ->
      `rail_monitor.bin`, 14% free
- [ ] Flash on the real ESP-BOX-3 + WiFi-only E2E vs the running server
      (Phase 5: hold-jog moves the rail, Home, live position, offline)
- [ ] Commit, push

> Built but not flashed (the BOX3 currently runs the older firmware).
> Phase 5 flashes it and drives the rail over WiFi against `server.py`.

---

## Task 18: on-device WiFi provisioning + port the existing BOX3 control UI

**Date**: 2026-06-24

### Purpose

Phase 5 surfaced two things on real hardware:
1. A hard-coded WiFi SSID is fragile (the placeholder had the wrong
   separator: `TP_Link_0624` vs the real `TP-Link_0624`). The user wants
   to pick the network on the device, like a phone -> **on-device touch
   provisioning (option B)**.
2. The control UI must match the **existing `ESP32S3BOX3MotorController`
   UI** (X/Z quadrant dial + Y buttons + Move plot + Status tabs), not the
   HotplateController-style panel, per the integration plan. The rail is
   the **Y axis**; X/Z stay as placeholders for the future pipette station.

### Checklist

- [x] `network.c/.h`: store credentials in NVS (`rail_wifi` namespace),
      load them at boot (NVS first, Kconfig fallback), `network_scan()`,
      `network_set_credentials()`, `network_clear_credentials()`,
      `network_has_credentials()`, and SSID/IP/RSSI/MAC getters for the
      Status tab. WiFi starts idle (no auto-connect) when uncredentialed.
- [x] `prov_ui.c/.h`: LVGL provisioning screen -- scanned-network list +
      on-screen keyboard for the password; on connect, hand off to the
      control UI. Kconfig WiFi defaults emptied so provisioning is the
      default path.
- [x] `main.c`: branch at boot -- provision when uncredentialed, else run.
      CONFIG long-press clears credentials and reboots (re-provision).
- [x] `ui.c`: faithful port of the `ESP32S3BOX3MotorController` 3-tab UI
      (Move / Jog Control / Status). **Y buttons -> rail jog over WiFi**
      (hold = continuous), **centre Home -> rail home**. X/Z dial + Move
      plot kept as pipette-station placeholders (no backend). Status tab
      shows WiFi (state/SSID/IP/RSSI/MAC) + rail server/position/age.
- [x] `idf.py build` clean (ESP-IDF v6.0.1, zero warnings)
- [x] Flash + on-device WiFi setup verified: picked `TP-Link_0624`, got
      `192.168.1.206`; server URL corrected to the real NUC IP
      `192.168.1.129:17052` (placeholder was `.16`)
- [x] **WiFi-only E2E verified on hardware (2026-06-24)**: BOX3 reaches
      `192.168.1.129:17052`; Y+/Y- jog and Home confirmed via server log
      (`POST /control/jog/start/{positive,negative}`, `/jog/stop`, 200 OK)
      and by eye on the rail

> NUC LAN IP is `192.168.1.129` (same host as the hotplate server); host
> publishes `:17052` to the LAN (alongside ssh `:17040`). The container
> only sees `172.17.0.2`, so the server URL must be the host LAN IP.

---

## Task 19: integrate the PID controller into the WiFi server

**Date**: 2026-06-24

### Purpose

The WiFi branch was cut from `main`, whose `LinearMotorController.py` uses
the old fixed-speed-schedule `move_to_mm`. The hardware-verified P
controller (Issue #11, branch `feature/issue-11-pid-controller`,
`9dc7b8e`) lives separately. Bring it into the WiFi branch so `server.py`
drives the rail with PID. No server change is needed: `server.py` only
calls the driver's public `move_to_mm` / `move_relative_mm`, so swapping
the driver makes the WiFi path use PID automatically.

### Checklist

- [x] Preserve `feature/issue-11-pid-controller` by pushing it to the fork
- [x] Bring `LinearMotorController.py` (PID version) into
      `feature/wifi-fastapi-server` (driver-only; #11's README/ToDo left out)
- [x] ruff clean + `py_compile` OK
- [x] **HW-verified through the WiFi server (2026-06-24)**: `POST
      /control/move {30}` converged to 30.030 mm and `home` to -0.067 mm;
      server log shows the P-controller loop (speed = kp*error, clamped to
      output_max=25): iter1 @25 -> iter2 @5 -> iter3 @1, |error| 0.03 mm

---

## Task 20: Repo layout cleanup (Modbus, ESP32S3, docs)

**Date**: 2026-07-27
**GitHub Issue**: #21 (Scope A refs #6)

### Purpose

Housekeeping over the repository layout, alongside the `pyproject.toml`
packaging work. Three unrelated pieces of drift, committed separately so
each stays revertible:

1. The Modbus variant was still in the tree after the project committed
   to the MINAS standard serial protocol only (`Pr5.37=0`). This is
   Scope C of Task 9 / #6.
2. `external/ESP32S3/` was a misleading home for the ESP-BOX-3 firmware
   from Tasks 17-18 -- nothing in it is external to this project, and
   the name collides with the convention of `external/` holding
   third-party or submodule code.
3. The motor accuracy sheet sat in the repository root under a Korean
   filename, against the §2 English-only documentation rule.

### Checklist

- [x] Delete `LinearMotorControllerModbus.py` + `Modbus_reference.pdf`
      (`1e6b105`, `refactor!` -- the module is a breaking removal)
- [x] Move `external/ESP32S3/` -> `controller/ESP32S3/` (`556d0de`);
      all 18 files recorded by git as renames, so no firmware was lost
- [x] Fix the two in-repo paths pointing at the old firmware location:
      `docs/server_api.md` L158 and `controller/ESP32S3/README.md` L54.
      L10 of that README still says `external/ESP32S3/` on purpose --
      it cites **HotplateController's** path, not this repo's
- [x] Rename `모터별_정확도_측정.xlsx - Sheet1.csv` ->
      `docs/Motor Movement Accuracy Analysis.xlsx - Sheet1.csv`
      (`7e7fc5f`); byte-identical, content unchanged
- [x] Pushed to `main` (`02561f8..7e7fc5f`)

### Verification

- [x] `git grep -ri modbus` clean across code and build config
      (documentation files still reference it -- see below)
- [x] `pyproject.toml` `only-include` entries all resolve to existing
      files; `import LinearMotorController` OK
- [x] `git show --numstat -M HEAD~1` -- 18 renames, the only content
      change being the one-line README path fix
- n/a `ruff check` -- no Python file was modified by this task. The only
      `.py` in the diff is the **deleted** Modbus module. The 10
      pre-existing errors in `claude_test/measure_accuracy.py`
      (E501/W291) are untouched and belong to Task 9 Scope B
- n/a Hardware run -- nothing here touches `LinearMotorController.py`
      or `server.py`

### Not done (deliberately)

Task 9 Scope C's documentation half is still open, tracked on #21:
`CLAUDE.md` L7 ("not Modbus" parenthetical) and the Reference Documents
rows for the deleted PDF, `LearnedPatterns.md` L22, marking Task 8
cancelled, and deleting `claude_test/check_input_signals.py`.
`MinasA6_driver_main.pdf` still awaits the user's confirmation before
deletion, per Scope C.

---

## 2026-07-28 — Retry read-only RS485 commands

Found while bringing up cell4 of the downstream InnoCORESDL project on
real hardware. A single MINAS handshake fails intermittently: sampling
the rail position through the cell server returned `None` **2 times in
20** (10%) with the rail otherwise healthy and no USB disconnects in the
kernel log. Because `move_to_mm` closes its loop on `read_position_mm`
every iteration, one lost read aborted an entire move — the first
operator-gated motion run failed part way through for this reason.

### Work items
- [x] Append this ToDo entry
- [ ] Create GitHub issue — **blocked**: no GitHub credentials on this
      host (`git push` fails with `could not read Username`)
- [x] Cut working branch `fix/rs485-read-retry`
- [x] Split the handshake out of `_send_and_receive` into `_exchange`,
      and make `_send_and_receive(block, attempts=1)` loop over it with
      a `retry_backoff_s` pause between tries
- [x] Apply `attempts=read_retry_attempts` (3) to the **four read-only**
      call sites only: `read_software_version`, `read_model_name`,
      `read_feedback_pulse_position`, `_read_parameter`
- [x] Deliberately leave `_acquire_execution_rights`,
      `_release_execution_rights` and `_write_parameter` single-shot —
      they are not idempotent, and re-sending one could apply a motion
      or parameter change twice. The default `attempts=1` preserves
      their existing behaviour exactly.
- [x] `ruff check` + `ruff format --check` pass
- [x] **Hardware-verified**: 30 consecutive position reads through the
      cell server, **0 failures** (was 2/20 before the change)
- [ ] Push branch, open PR per §15.2 — blocked on the same credentials

---

## 2026-07-28 — Make move_to_mm report arrival, not just position

Follow-up to the retry work above, from the same cell4 bring-up. The
first full motion run reached its last step and failed:
`move_back` was commanded to 0.0 mm, the rail stopped at **0.676 mm**,
and the cell above reported `200 OK` — because `move_to_mm` returned a
bare float on *every* exit path, so "converged at 0.0" and "gave up at
0.676" were the same value to a caller.

### Work items
- [x] Append this ToDo entry
- [ ] Create GitHub issue — **blocked**: no GitHub credentials on this
      host (`git push` → `could not read Username`)
- [x] Add a frozen `MoveResult` dataclass (`position_mm`, `converged`,
      `reason`) and return it from every `move_to_mm` exit
- [x] Soften the stall detector: `stall_patience = 3` consecutive
      non-improving iterations instead of aborting on the first one.
      A single stalled correction is normal on a servo; the old
      behaviour abandoned real moves on noise. The improvement baseline
      (`prev_abs_error`) now only advances on an actual improvement.
- [x] Raise `max_iterations` 5 → 12 so the extra patience has room
- [x] Update `server.py`, the only in-repo caller: a non-converged move
      now sets `state="error"` with the position it actually stopped at,
      instead of reporting `idle` at the wrong place
- [x] `ruff check` + `ruff format --check` pass on both files
- [x] Contract verified without hardware: `converged` returns the
      position; `stalled` and `iteration_cap` raise in the downstream
      cell; `None` still raises the transport error
- [ ] Re-run the full motion scenario to confirm the return leg now
      converges (operator-gated; the run needs a console confirmation)
- [ ] Push branch, open PR per §15.2 — blocked on the same credentials

---

## 2026-07-28 — Retry and verify the stop command

Found while diagnosing why a 50 mm move oscillated and stalled at
48.592 mm. The per-iteration log showed corrections travelling far
further than commanded — `move +1.408 mm @ speed 6` moved **13.0 mm**.

### Root cause
`move_relative`'s `finally` block called
`self._write_parameter(3, 4, 0)` and **discarded the return value**.
`_write_parameter` returns `False` on a failed RS485 exchange, so at the
bench's error rate the stop silently did not happen and the rail kept
running at the commanded speed until some later call wrote a different
one.

Measured on the real amp: a single-shot zero-speed write succeeded
**28 times in 30** — roughly one stop in fifteen was being lost.

An earlier note in this file claimed writes must never be retried
because they are not idempotent. That is right for positioning writes
and wrong for this one: **writing speed 0 twice is identical to writing
it once**, and it is the write whose failure matters most.

### Work items
- [x] Append this ToDo entry
- [x] Add `_stop_motion()`: retries the zero-speed write up to
      `stop_attempts` (5) and reports whether the amp acknowledged
- [x] `move_relative` now raises `MotionStopError` when the stop cannot
      be confirmed, instead of returning normally as if it had stopped
- [x] Keep every other write single-shot — the idempotency argument
      still holds for them
- [x] `ruff check` + `ruff format --check` pass
- [x] **Hardware-verified**: single-shot stop 28/30; `_stop_motion`
      **30/30**; rail position unchanged (0.175 → 0.175 mm) across 60
      zero-speed writes, confirming the write is idempotent
- [ ] Create GitHub issue — operator has now run `gh auth login`; file
      this together with the two earlier entries
- [ ] Re-run the 50 mm scenario to confirm the oscillation is gone
      (operator-gated)

---

## 2026-07-28 — Retry the execution-rights exchange too

A 50 mm return leg aborted before it moved:

```
iter 1: move -50.023 mm @ speed 25 r/min
Start=50023, Target=0
Response block receive timeout.
iter 1: move_relative_mm failed.
```

`Start=` printed but `Final=` did not, which places the failure in
`_acquire_execution_rights()` — left at `attempts=1` by the earlier retry
work on the grounds that "writes are not idempotent".

That grouping was wrong twice in one session (see also the stop write).
Acquiring or releasing the control token **moves nothing**, and asking
for it twice leaves the amp exactly as asking once would. The right split
is by *what re-sending actually does*, not by the read/write label.

### Work items
- [x] Append this ToDo entry
- [x] `_acquire_execution_rights` / `_release_execution_rights` now pass
      `attempts=read_retry_attempts`
- [x] Rewrite the `_send_and_receive` docstring, which stated the wrong
      rule: it now classifies by effect, and records that the speed write
      (`Pr3.04`) alone stays single-shot because its re-send starts motion
- [x] `ruff check` + `ruff format --check` pass
- [x] **Hardware-verified** on the real amp: single-shot acquire
      **39/40** (that one failure aborts a whole move); with retry
      **40/40** acquire and **40/40** release. Rail unmoved across all
      120 exchanges (50.016 → 50.016 mm), confirming the token
      operations are motion-free.
- [x] Parent suite still green: `pytest` 32 pass, 5/5 cell contract cases
- [ ] Confirm on a full 50 mm round trip (operator-gated)

---

## 2026-07-28 — Bound one handshake attempt (exchange_timeout_s)

The retry added earlier raised reliability without bounding latency, and
the first scenario run to reach the balance died on its **first** step:

```
No EOT response from amplifier.     <- attempt 1 (2 s)
No EOT response from amplifier.     <- attempt 2 (2 s)
No EOT response from amplifier.     <- attempt 3 (2 s)
cell4 GET status timed out after 5.0s
```

Three attempts at the port's 2 s timeout is over six seconds, so a plain
`GET /v1/status` could exceed a scenario's 5 s step timeout. Retrying was
right; leaving each attempt on a 2 s budget was not.

### Work items
- [x] Append this ToDo entry
- [x] Add `exchange_timeout_s = 0.3`. A whole exchange normally costs
      ~26 ms (a 24-byte reply at 9600 bps is ~25 ms), so this is ten
      times the honest cost of a good read.
- [x] Split the handshake into `_handshake`; `_exchange` now sets the
      port timeout to the budget and restores it in a `finally`, and both
      EOT/ENQ wait loops use the budget instead of a hardcoded 2 s
- [x] `ruff check` + `ruff format --check` pass; parent suite still
      32 pass
- [x] **Verified without hardware** (the rail adapter is in an EPROTO
      fault, see below): one attempt bounded at 0.31 s; the handshake
      uses the short timeout; the original is restored, including on the
      exception path; **three attempts total 1.02 s, down from 6 s+** —
      which is the specific failure above, fixed.
- [ ] **Not yet measured on hardware**: the success rate at a 0.3 s
      budget, and whether it shrinks `move_relative`'s poll-loop blind
      window enough to reduce the per-iteration overshoot. 0.3 s is ten
      times the median read, but that is arithmetic, not a measurement.
- [ ] Push branch, open PR (issue #23 covers this work)

### Bench note — the adapter, not the software

The Moxa UPort 1150 failed **four times today**, each time needing a
physical re-plug and recurring within minutes. Kernel logs ~20,000
`urb status -71` (EPROTO) per minute while it is faulted, and once wedged
the port cannot even be opened (`ti_open - cannot send open command,
-71`). The balance on the same bus is unaffected throughout, so this is
the adapter or its cabling, not the bus and not this driver. Worth
correcting an earlier reading of mine: the three consecutive EOT misses
above looked like retry latency alone, but three in a row is ~0.1% by
chance at the measured ~10% single-read failure rate — the adapter was
already degrading when that run started.
