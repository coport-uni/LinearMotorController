# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Panasonic MINAS A6 series servo amplifier controller for linear rail systems. Communicates with the servo amp over RS485 using the **MINAS 표준 프로토콜** (standard serial protocol), not Modbus.

## Environment

This project runs inside a **Docker container** with [Claude Code](https://claude.ai/code) as the primary development tool.

| Item              | Detail                                         |
|-------------------|-------------------------------------------------|
| Runtime           | Docker container (`--privileged`)               |
| OS                | Ubuntu 24.04 (Noble)                            |
| Dev tool          | Claude Code (CLI / VS Code extension)           |

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

---

## 1. MIT Code Convention

All code follows the [MIT CommLab Coding and Comment Style](https://mitcommlab.mit.edu/broad/commkit/coding-and-comment-style/).

### Naming

- **Variables and classes** are nouns; **functions and methods** are verbs.
- Names must be pronounceable and straightforward.
- Name length is proportional to scope: short for local, descriptive for broad.
- Avoid abbreviations unless self-explanatory. If unavoidable, define them in a comment block.
- Python conventions:

| Element    | Style        | Example               |
|------------|--------------|-----------------------|
| Variable   | `lower_case` | `joint_angle`         |
| Function   | `lower_case` | `send_action`         |
| Class      | `CamelCase`  | `FairinoFollower`     |
| Constant   | `lower_case` | `_settle_mid_s`       |
| Module     | `lowercase`  | `fairino_follower`    |

### Structure

- **80-column limit** for all new code.
- One statement per line.
- Indent with **4 spaces** (never tabs).
- Place operators on the **left side** of continuation lines so the reader can see at a glance that a line continues.
- Group related items visually with alignment.
- Use refactoring-invariant alignment for long argument lists:
  ```python
  result = some_function(
      argument_one,
      argument_two,
      argument_three)
  ```

### Spacing

- One space after commas, none before: `foo(a, b, c)`.
- One space on each side of `=`, `==`, `<`, `>`, etc.
- Be consistent with arithmetic operators within a file.

### Comments

- Use **complete sentences**.
- Only comment for **context** or **non-obvious choices**. Never restate what the code already says.
- Outdated comments are worse than none. Keep them current or delete them.
- TODO format:
  ```python
  # TODO: (@owner) Implement 2-step predictor-corrector
  # for stability. Adams-Bashforth causes shocks.
  ```

### Language

- All code comments, docstrings, commit messages, documentation files (including README), **GitHub issues, and pull requests** must be written in **English**.

### Documentation

- All public functions and classes must have **docstrings** (PEP 257 / Google style).
- Use `"""triple double quotes"""`.
- A docstring states **what** and **why**, not **how**.
- Write as imperative: `"""Return the pathname."""` not `"""Returns the pathname."""`
- Do not restate the function signature in the docstring.
- Include `Args:`, `Returns:`, and `Raises:` sections when applicable.
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

---

## 2. Debug File Management

All debug, exploratory, and throwaway test scripts must be saved in `claude_test/`, **not** in `tests/`.

### Rules

| Location        | What goes there                                      |
|-----------------|------------------------------------------------------|
| `tests/`        | Production-quality tests that are part of CI/CD.     |
| `claude_test/`  | Debug scripts, one-off experiments, diagnostic code. |

### When writing debug code

1. Create the file directly in `claude_test/` (e.g., `claude_test/debug_servo_timing.py`).
2. Add a one-line docstring at the top explaining the purpose.
3. If the debug script leads to a real fix, move the relevant parts into a proper test under `tests/` and delete or archive the debug version.

### README

`claude_test/README.md` is the index. When adding a new debug file, add a row to the table in that README describing what the file does and what was learned.

---

## 3. Task Management

> **MANDATORY**: This workflow applies to **every task without exception**, regardless of size or complexity. No task may begin without writing `ToDo.md` and creating a GitHub issue via `gh`. Skipping any step is not allowed.

### Rules

1. **Write ToDo.md**: For every task requested by the user, create a `ToDo.md` file and confirm the contents with the user before starting work.
2. **Accumulate ToDo.md**: Do not overwrite previous entries in `ToDo.md`. Always **append** new tasks below existing ones so that the file serves as a cumulative command history for Claude's actions.
3. **Register GitHub issues**: When possible, use the `gh` CLI to register the Todo list and details as a GitHub issue.

### Command Input Validation

Before writing ToDo.md, the following two checks must be performed:

1. **Is the command explicit?**: If the request is ambiguous or open to interpretation, do not start work. Instead, ask the user for specifics:
   - What is being changed? (target)
   - How is it being changed? (method)
   - Why is it being changed? (purpose)
2. **Are there reference materials?**: Check whether related PDFs, websites, or documents exist. If so, review them before incorporating into the work.

> Do not proceed if either check is not satisfied.

### Workflow

1. Receive the user's task request and **validate the command input**.
2. Once validated, organize the task list in `ToDo.md`.
3. Get the user's confirmation on the `ToDo.md` contents.
4. Once confirmed, create a GitHub issue via `gh issue create`.
5. Check off completed items in `ToDo.md` as work progresses.
6. Update the GitHub issue via `gh issue edit` for completed items.
7. **Commit and push** changes after every user command is completed.

> **Reminder**: Steps 2 (`ToDo.md`) and 4 (`gh issue create`) are **non-negotiable**. Every task must have a corresponding `ToDo.md` entry and a GitHub issue before any work begins.

---

## 4. Testing Rules

Tests exist to verify the **correctness and quality** of code. Code quality must never be sacrificed just to pass tests.

### Rules

1. **No magic numbers**: Do not use arbitrary numbers or values directly to pass tests. All values must be defined as meaningful constants or variables.
   ```python
   # Bad: passing tests with magic numbers
   def calculate_area(radius):
       return 3.14 * radius * radius  # Why 3.14?

   # Good: use meaningful constants
   import math

   def calculate_area(radius):
       return math.pi * radius * radius
   ```

2. **No hardcoding**: Do not hardcode values to match expected test results. Code must work through correct logic, not through branches or fixed values tailored to specific inputs.
   ```python
   # Bad: hardcoded to match test inputs
   def convert_temperature(celsius):
       if celsius == 100:
           return 212
       if celsius == 0:
           return 32
       return celsius * 1.8 + 32

   # Good: correct logic implementation
   def convert_temperature(celsius):
       return celsius * 1.8 + 32
   ```

3. **Code quality first**: Prioritize readability, maintainability, and correctness over whether tests pass. If a test fails, fix the logic correctly rather than tricking the test.

---

## 5. Linting

All Python code must pass **Ruff** checks before committing.

### Rules

1. **Line length**: 80 columns (`line-length = 80` in `ruff.toml`).
2. **Run on every commit**: Before committing, run:
   ```bash
   ruff check <file>.py
   ruff format --check <file>.py
   ```
3. **Fix before committing**: If either command reports errors, fix them before proceeding. Use `ruff format <file>.py` to auto-format.

---

## Reference Documents (PDFs in repo)

- `MinasA6_드라이버.pdf` — Modbus통신사양·Block동작기능편 (SX-DSV03384). Register addresses for Modbus mode.
- `MinasA6_드라이버_참고.pdf` — 취급설명서(종합편). Contains MINAS standard protocol spec (P.7-28~7-41), command details, parameter list, wiring diagrams.
- `Modbus_참조.pdf` — Additional Modbus reference.
