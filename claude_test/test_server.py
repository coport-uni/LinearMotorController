"""Offline test for the FastAPI server's RailMonitor logic.

Runs with no hardware: a fake controller stands in for
LinearMotorController, and RailMonitor's snapshot / move / jog / home
behaviour is checked directly (the FastAPI endpoints are thin wrappers
over these, mapping RailRangeError -> 422 and RailCommError -> 503).
Exit code is non-zero if any check fails.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402

# Poll fast so the threaded jog checks run quickly.
server.jog_watch_interval_s = 0.01


class FakeController:
    """In-memory stand-in for LinearMotorController."""

    def __init__(self, position_mm=0.0):
        self.position_mm = position_mm
        self.calls = []
        self.param_writes = []

    def read_position_mm(self):
        return self.position_mm

    def move_to_mm(self, target_mm, **kwargs):
        self.calls.append(("move_to_mm", target_mm))
        self.position_mm = target_mm
        return target_mm

    def _acquire_execution_rights(self):
        return True

    def _write_parameter(self, category, number, value):
        self.param_writes.append((category, number, value))
        return True

    def _release_execution_rights(self):
        return True


class FailingController(FakeController):
    """A controller whose reads always fail, as if disconnected."""

    def read_position_mm(self):
        return None


def wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def new_monitor(position_mm=0.0):
    """Build a RailMonitor over a fake controller, snapshot filled once."""
    fake = FakeController(position_mm)
    monitor = server.RailMonitor(fake)
    monitor.poll_once()
    return monitor, fake


results = []


def check(name, ok):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}")


# poll_once reports a connected snapshot with the read position + age.
monitor, fake = new_monitor(12.5)
status = monitor.current_status()
check(
    "status: connected snapshot with position + age",
    status["connected"] is True
    and status["position_mm"] == 12.5
    and status["state"] == "idle"
    and "age_seconds" in status,
)

# move within limits drives move_to_mm and reports the new position.
monitor, fake = new_monitor(0.0)
status = monitor.move(50.0)
check(
    "move within limits -> move_to_mm(50)",
    fake.calls == [("move_to_mm", 50.0)]
    and status["position_mm"] == 50.0
    and status["state"] == "idle",
)

# move outside the soft envelope raises RailRangeError (endpoint -> 422).
monitor, fake = new_monitor(0.0)
raised = False
try:
    monitor.move(server.rail_max_mm + 100.0)
except server.RailRangeError:
    raised = True
check("move out-of-limit raises RailRangeError", raised)

# home maps to move_to_mm(0).
monitor, fake = new_monitor(50.0)
monitor.home()
check("home -> move_to_mm(0)", ("move_to_mm", 0.0) in fake.calls)

# jog_start drives a continuous +jog_speed; jog_stop returns Pr3.04 to 0.
monitor, fake = new_monitor(50.0)
monitor.jog_start(1)
started = wait_until(
    lambda: (
        monitor._jog_active and (3, 4, server.jog_speed) in fake.param_writes
    )
)
check("jog_start(+1) writes Pr3.04 = +jog_speed", started)
monitor.jog_stop()
if monitor._jog_thread is not None:
    monitor._jog_thread.join(timeout=2.0)
check(
    "jog_stop returns Pr3.04 to 0",
    fake.param_writes[-1] == (3, 4, 0) and not monitor._jog_active,
)

# jog_start(-1) drives the negative direction.
monitor, fake = new_monitor(50.0)
monitor.jog_start(-1)
negative = wait_until(lambda: (3, 4, -server.jog_speed) in fake.param_writes)
monitor.jog_stop()
if monitor._jog_thread is not None:
    monitor._jog_thread.join(timeout=2.0)
check("jog_start(-1) writes Pr3.04 = -jog_speed", negative)

# a jog from the upper soft limit is refused (endpoint -> 422).
monitor, fake = new_monitor(server.rail_max_mm)
raised = False
try:
    monitor.jog_start(1)
except server.RailRangeError:
    raised = True
check("jog_start at upper limit raises RailRangeError", raised)

# a failing read keeps the server up with a disconnected snapshot.
fail = FailingController()
monitor = server.RailMonitor(fail)
monitor.poll_once()
status = monitor.current_status()
check(
    "disconnected device -> connected False, server stays up",
    status["connected"] is False,
)

passed = sum(results)
print(f"\nSUMMARY: {passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
