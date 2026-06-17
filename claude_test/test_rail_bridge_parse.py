"""Offline test for rail_bridge command parsing and soft limits.

Runs with no hardware: it swaps rail_bridge._rail for a fake that
records calls, then drives box3_dispatch and checks the CMD:* mapping
and the soft-limit refusals. Exit code is non-zero if any check fails.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rail_bridge  # noqa: E402


class FakeRail:
    """Stand-in for LinearMotorController that records motion calls."""

    def __init__(self, position_mm=0.0):
        self.position_mm = position_mm
        self.calls = []

    def move_to_mm(self, target_mm, **kwargs):
        self.calls.append(("move_to_mm", target_mm))
        self.position_mm = target_mm
        return target_mm

    def move_relative_mm(self, distance_mm, **kwargs):
        self.calls.append(("move_relative_mm", distance_mm))
        self.position_mm += distance_mm
        return self.position_mm

    def read_position_mm(self):
        return self.position_mm


def setup(position_mm=0.0):
    fake = FakeRail(position_mm)
    rail_bridge._rail = fake
    rail_bridge._set_state(
        position_mm=position_mm, state="idle", connected=True, target_mm=None
    )
    return fake


results = []


def check(name, ok):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}")


# Absolute move maps to move_to_mm with the parsed float value.
fake = setup(0.0)
rail_bridge.box3_dispatch("MOVE X 123")
check("MOVE X 123 -> move_to_mm(123.0)", fake.calls == [("move_to_mm", 123.0)])

# Jog +/- map to one fixed relative step each.
fake = setup(50.0)
rail_bridge.box3_dispatch("X+")
check(
    "X+ -> move_relative_mm(+step)",
    fake.calls == [("move_relative_mm", rail_bridge.jog_step_mm)],
)

fake = setup(50.0)
rail_bridge.box3_dispatch("X-")
check(
    "X- -> move_relative_mm(-step)",
    fake.calls == [("move_relative_mm", -rail_bridge.jog_step_mm)],
)

# Stop is a no-op: the step move has already finished and self-stopped.
fake = setup(50.0)
rail_bridge.box3_dispatch("X0")
check("X0 -> no rail call", fake.calls == [])

# Home maps to move_to_mm(home_target_mm).
fake = setup(50.0)
rail_bridge.box3_dispatch("HOME")
check(
    "HOME -> move_to_mm(0.0)",
    fake.calls == [("move_to_mm", rail_bridge.home_target_mm)],
)

# An absolute move past the soft limit is refused (no rail call).
fake = setup(0.0)
rail_bridge.box3_dispatch(f"MOVE X {rail_bridge.rail_max_mm + 100:.0f}")
check("out-of-limit MOVE refused", fake.calls == [])

# A jog that would cross the soft limit is refused.
fake = setup(rail_bridge.rail_max_mm - 1.0)
rail_bridge.box3_dispatch("X+")
check("out-of-limit jog refused", fake.calls == [])

# Malformed and unknown lines are ignored without crashing.
fake = setup(0.0)
rail_bridge.box3_dispatch("MOVE X abc")
rail_bridge.box3_dispatch("GARBAGE")
check("malformed/unknown ignored", fake.calls == [])

passed = sum(results)
print(f"\nSUMMARY: {passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
