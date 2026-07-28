"""Unit tests for reconnecting after the USB link drops.

No hardware and no serial port: every test builds the controller with
``object.__new__`` and injects a fake port, because ``__init__`` opens a
real device.

The behaviour under test came from a bench where the servo amp coupled
noise back into its own RS485 link, so the adapter re-enumerated every
few seconds. Two failure modes followed, and they need opposite
treatment:

* A read on the stale file descriptor fails with ``EIO`` **forever**,
  because the fd outlives the device node. Reopening is right.
* A move that straddles a reconnect ran blind for an unknown window with
  a speed command latched in the amp. Resuming it is wrong at any cost.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from LinearMotorController import (  # noqa: E402
    LinearMotorController,
    LinkDroppedError,
    MotionStopError,
    SpeedCommandError,
)

#: The module, not the class -- they share a name, so aliasing the import
#: would be the confusing way to say this. Needed to monkeypatch
#: `resolve_port` and `serial` where `_open_serial` looks them up.
lmc_module = sys.modules[LinearMotorController.__module__]

START_MM = 0.0
TARGET_MM = 50.0


class FakePort:
    """Just enough of ``serial.Serial`` for ``_exchange`` to run."""

    def __init__(self, raise_on_timeout_set: bool = False) -> None:
        self.timeout = 2
        self.closed = False
        self._raise = raise_on_timeout_set

    def __setattr__(self, name: str, value: object) -> None:
        if name == "timeout" and getattr(self, "_raise", False):
            raise OSError(5, "Input/output error")
        object.__setattr__(self, name, value)

    def close(self) -> None:
        self.closed = True


def _controller(port: FakePort | None = None) -> LinearMotorController:
    """Build a controller without opening a real serial device."""
    lmc = object.__new__(LinearMotorController)
    lmc._port_spec = "110A:1150"
    lmc.link_generation = 0
    lmc.ser = port if port is not None else FakePort()
    lmc.id = 1
    lmc.ENQ, lmc.EOT, lmc.ACK, lmc.NAK = 0x05, 0x04, 0x06, 0x15
    return lmc


# ── reopening ────────────────────────────────────────────────────────


def test_reopen_bumps_link_generation() -> None:
    lmc = _controller()
    lmc._open_serial = lambda: FakePort()

    assert lmc._reopen() is True
    assert lmc.link_generation == 1


def test_reopen_reports_failure_without_bumping_generation() -> None:
    """A failed reopen must not look like a successful one."""
    lmc = _controller()

    def _fail() -> FakePort:
        raise RuntimeError("no serial adapter connected")

    lmc._open_serial = _fail

    assert lmc._reopen() is False
    assert lmc.link_generation == 0


def test_exchange_reopens_on_os_error_and_reports_no_reply() -> None:
    """The bench signature: setting the timeout raises EIO on a node
    that was deleted by a re-enumeration."""
    lmc = _controller(FakePort(raise_on_timeout_set=True))
    lmc._open_serial = lambda: FakePort()

    assert lmc._exchange(b"") is None
    assert lmc.link_generation == 1


def test_open_serial_waits_out_a_re_enumeration_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """resolve_port() raising during a gap is transient, not fatal.

    This is the startup failure it fixes: the cell server failed to
    start on 3 of 4 consecutive attempts purely because it looked while
    the adapter was between enumerations.
    """
    lmc = _controller()
    lmc.open_retry_delay_s = 0.0
    attempts: list[int] = []

    def _flaky_resolve(_port: str) -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("no serial adapter connected")
        return "/dev/ttyUSB3"

    monkeypatch.setattr(lmc_module, "resolve_port", _flaky_resolve)
    monkeypatch.setattr(
        lmc_module.serial, "Serial", lambda **_kwargs: FakePort()
    )

    assert isinstance(lmc._open_serial(), FakePort)
    assert len(attempts) == 3


def test_open_serial_gives_up_and_names_the_last_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An adapter that never returns must still fail, loudly. "Absent"
    and "present but unopenable" need different bench actions, so the
    underlying error has to survive into the message."""
    lmc = _controller()
    lmc.open_retry_delay_s = 0.0
    lmc.open_retry_attempts = 3

    def _always_absent(_port: str) -> str:
        raise RuntimeError("no serial adapter connected")

    monkeypatch.setattr(lmc_module, "resolve_port", _always_absent)

    with pytest.raises(RuntimeError, match="no serial adapter connected"):
        lmc._open_serial()


# ── the safety rule: never resume a move across a reconnect ──────────


def test_move_survives_when_the_link_never_dropped() -> None:
    lmc = _controller()
    lmc.read_position_mm = lambda: TARGET_MM
    result = lmc.move_to_mm(TARGET_MM)

    assert result is not None
    assert result.converged is True


def test_abort_raises_link_dropped_when_the_stop_lands() -> None:
    lmc = _controller()
    lmc._stop_motion = lambda: True
    lmc.link_generation = 1

    with pytest.raises(LinkDroppedError):
        lmc._abort_if_link_dropped(0)


def test_abort_raises_motion_stop_when_the_stop_does_not_land() -> None:
    """Worse case: link came back but the rail would not stop."""
    lmc = _controller()
    lmc._stop_motion = lambda: False
    lmc.link_generation = 1

    with pytest.raises(MotionStopError):
        lmc._abort_if_link_dropped(0)


def test_abort_is_a_no_op_while_the_link_holds() -> None:
    lmc = _controller()
    lmc._stop_motion = lambda: pytest.fail("must not stop a healthy move")

    lmc._abort_if_link_dropped(lmc.link_generation)


def test_move_to_mm_aborts_instead_of_resuming_after_a_drop() -> None:
    """The whole point: a drop mid-move fails the move, and the rail is
    stopped rather than driven on stale position data."""
    lmc = _controller()
    stops: list[int] = []
    lmc._stop_motion = lambda: (stops.append(1), True)[1]
    lmc.read_position_mm = lambda: START_MM

    def _move(*_args: object, **_kwargs: object) -> int:
        lmc.link_generation += 1  # the adapter re-enumerated mid-move
        return 0

    lmc.move_relative_mm = _move

    with pytest.raises(LinkDroppedError):
        lmc.move_to_mm(TARGET_MM)
    assert stops, "the rail must be stopped before the move is abandoned"


def test_reconnect_before_motion_does_not_abort_the_move() -> None:
    """A reopen while merely establishing position is not a drop
    *during* the move -- nothing was in motion yet."""
    lmc = _controller()
    lmc._stop_motion = lambda: pytest.fail("nothing was moving")
    lmc.read_position_mm = lambda: TARGET_MM
    lmc.link_generation += 1  # the reopen happened before the call
    result = lmc.move_to_mm(TARGET_MM)

    assert result is not None
    assert result.converged is True


# ── a move that was never commanded is not a stall ──────────────────


def _movable(lmc: LinearMotorController, write_ok: bool) -> list[int]:
    """Wire up move_relative with a speed write that succeeds or not."""
    writes: list[int] = []

    def _write(cls: int, num: int, value: int) -> bool:
        if (cls, num) == (3, 4) and value != 0:
            writes.append(value)
            return write_ok
        return True  # the zero-speed stop always lands here

    lmc._write_parameter = _write
    lmc._acquire_execution_rights = lambda: True
    lmc._release_execution_rights = lambda: True
    lmc.read_feedback_pulse_position = lambda: 0
    return writes


def test_unacknowledged_speed_write_is_not_reported_as_a_stall() -> None:
    """The bench failure this came from: the rail never moved, and the
    driver called it 'stalled', which reads as 'the servo fought the
    load' and sends an operator to the limit switches."""
    lmc = _controller()
    _movable(lmc, write_ok=False)

    with pytest.raises(SpeedCommandError):
        lmc.move_relative(50_000, speed=25, timeout=10.0)


def test_a_failed_speed_write_does_not_burn_the_timeout() -> None:
    """Polling a rail that was never told to move is pure waiting: it
    turned an instant failure into 36 s on the bench."""
    lmc = _controller()
    _movable(lmc, write_ok=False)
    polls = 0

    def _count() -> int:
        nonlocal polls
        polls += 1
        return 0

    lmc.read_feedback_pulse_position = _count

    with pytest.raises(SpeedCommandError):
        lmc.move_relative(50_000, speed=25, timeout=10.0)
    # One read to establish the start position, and no poll loop.
    assert polls == 1


def test_stop_failure_outranks_a_failed_speed_write() -> None:
    """If both go wrong the operator must hear the one that means the
    rail might be moving."""
    lmc = _controller()
    _movable(lmc, write_ok=False)
    lmc._stop_motion = lambda: False

    with pytest.raises(MotionStopError):
        lmc.move_relative(50_000, speed=25, timeout=10.0)


def test_an_acknowledged_speed_write_still_moves() -> None:
    lmc = _controller()
    writes = _movable(lmc, write_ok=True)
    lmc._stop_motion = lambda: True

    assert lmc.move_relative(50_000, speed=25, timeout=0.05) == 0
    # Sign comes from the offset, so a forward move writes +25.
    assert writes == [25]


def test_a_zero_offset_is_treated_as_a_reverse_move() -> None:
    """Not a bug being asserted as behaviour -- a quirk worth pinning.
    `direction = 1 if pulse_offset > 0 else -1` makes a zero offset move
    *backwards* at the given speed. move_to_mm never does this (it
    returns on tolerance first), but a direct caller would, and would
    not expect it."""
    lmc = _controller()
    writes = _movable(lmc, write_ok=True)
    lmc._stop_motion = lambda: True

    lmc.move_relative(0, speed=25, timeout=0.05)
    assert writes == [-25]
