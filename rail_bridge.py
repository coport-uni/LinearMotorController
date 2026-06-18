"""Bridge the ESP32-S3-BOX-3 touch UI to the linear rail.

The BOX3 firmware emits newline-framed ASCII commands over USB serial:

    CMD:X+        jog one fixed step, positive
    CMD:X-        jog one fixed step, negative
    CMD:X0        stop / no-op (a step move has already finished)
    CMD:MOVE X <mm>   absolute move to <mm>
    CMD:HOME      return to the power-on origin (0 mm)

This bridge reads those lines, maps them onto LinearMotorController
motion calls, pushes "POS:<mm>" back to the BOX3 for a live display,
and serves rail status over HTTP so the ESP32 web monitor can poll it.

It mirrors the structure of the sibling ESP32S3BOX3MotorController
bridge.py (one lock, a dispatch table, an HTTP server in a daemon
thread, a reconnect loop), but reads pyserial instead of TCP and drives
the MINAS rail instead of MKS CAN motors.

Run: python3 rail_bridge.py     (Ctrl+C to stop)

The rail's /dev/ttyUSB* number is not stable; leave rail_port = None to
auto-probe (see claude_test/probe_ports.py). The BOX3 enumerates
separately as /dev/ttyACM*.
"""

import glob
import sys
import threading
import time

import serial

from LinearMotorController import LinearMotorController

# --- Configuration ---------------------------------------------------------
# Rail RS485-over-FTDI port. None auto-probes /dev/ttyUSB* with the same
# MINAS model-name read used by claude_test/probe_ports.py, because the
# numbering is not stable across re-enumeration (LP 5).
rail_port = None
rail_port_glob = "/dev/ttyUSB*"

# BOX3 USB CDC serial. The S3-BOX-3 console enumerates as /dev/ttyACM*.
box3_serial_port = "/dev/ttyACM0"
box3_baud = 115200
box3_serial_timeout_s = 1.0

# Step-jog: one fixed relative move per CMD:X+/CMD:X- press, since the
# MINAS protocol has only blocking moves (no continuous jog).
jog_step_mm = 5.0  # distance moved per +/- button press
jog_speed = 25  # r/min; low speed keeps move_relative overshoot small
jog_tolerance_mm = 0.5  # stop band for a jog step
jog_timeout_s = 20.0  # abort a jog if it does not settle in time

# Absolute move (CMD:MOVE X <mm>) and CMD:HOME -> move_to_mm(0.0).
# move_to_mm is the accurate closed-loop primitive (LP 2).
move_tolerance_mm = 0.1  # closed-loop stop band for absolute moves
move_max_iterations = 1  # closed-loop passes (1 = single pass)
move_timeout_per_step_s = 10.0  # abort a pass if it does not settle
home_target_mm = 0.0  # power-on origin

# Soft travel limits enforced here -- LinearMotorController has none.
# CALIBRATE to the physical rail before enabling motion on hardware.
rail_min_mm = 0.0
rail_max_mm = 190.0  # reject targets beyond this soft ceiling

# HTTP status/control plane for the web monitor.
http_port = 8001

# Position feedback cadence: POS:<mm> push + /status cache refresh.
pos_push_interval_s = 0.5  # seconds between rail position reads/pushes

# Reconnect backoff for the BOX3 serial link.
reconnect_delay_s = 2.0

# --- Shared state ----------------------------------------------------------
# _rail_lock serializes every LinearMotorController call: its moves are
# blocking, so an absolute move can hold the lock for several seconds.
# The feedback reader and HTTP /status therefore read the lightweight
# _state cache instead of contending for _rail_lock during a move.
_rail_lock = threading.Lock()
_rail = None

_box3_lock = threading.Lock()
_box3_serial = None

_state_lock = threading.Lock()
_state = {
    "position_mm": None,
    "state": "idle",
    "target_mm": None,
    "connected": False,
}


def _set_state(**fields):
    """Merge the given fields into the shared status cache."""
    with _state_lock:
        _state.update(fields)


def _within_limits(target_mm):
    """Return whether target_mm is inside the soft travel envelope."""
    return rail_min_mm <= target_mm <= rail_max_mm


def _finish_move(result):
    """Translate a move_* return value into the status cache.

    move_relative_mm and move_to_mm return the final mm position on
    success and None on any RS485 failure (they never raise).
    """
    if result is None:
        _set_state(state="error", connected=False)
        print("[RAIL] move returned None (RS485 failure)")
        return
    _set_state(position_mm=result, state="idle", connected=True)


def _jog(step_mm):
    """Execute one fixed relative step, refusing out-of-limit moves.

    The prospective absolute target is computed from the last known
    position; if the position is unknown the step is refused so the rail
    is never nudged blindly past a soft limit.
    """
    with _state_lock:
        base = _state["position_mm"]
    if base is None:
        print("[JOG] refused: current position unknown")
        return
    target = base + step_mm
    if not _within_limits(target):
        print(
            f"[JOG] refused: {target:.3f} mm outside "
            f"[{rail_min_mm}, {rail_max_mm}]"
        )
        return
    _set_state(state="moving", target_mm=target)
    with _rail_lock:
        result = _rail.move_relative_mm(
            step_mm,
            speed=jog_speed,
            tolerance_mm=jog_tolerance_mm,
            timeout=jog_timeout_s,
        )
    _finish_move(result)


def _move_to(target_mm):
    """Move to an absolute target, refusing out-of-limit requests."""
    if not _within_limits(target_mm):
        print(
            f"[MOVE] refused: {target_mm:.3f} mm outside "
            f"[{rail_min_mm}, {rail_max_mm}]"
        )
        return
    _set_state(state="moving", target_mm=target_mm)
    with _rail_lock:
        result = _rail.move_to_mm(
            target_mm,
            tolerance_mm=move_tolerance_mm,
            max_iterations=move_max_iterations,
            timeout_per_step=move_timeout_per_step_s,
        )
    _finish_move(result)


def _home():
    """Return to the power-on origin (no MINAS homing sensor exists)."""
    _move_to(home_target_mm)


_box3_routes = {
    "X+": lambda: _jog(jog_step_mm),
    "X-": lambda: _jog(-jog_step_mm),
    "X0": lambda: None,
    "HOME": _home,
}


def box3_dispatch(cmd):
    """Route one CMD:* payload (the part after "CMD:") from the BOX3.

    The absolute "MOVE X <mm>" form is handled first, then the fixed
    step-jog / home table. Unknown commands are ignored, matching the
    sibling bridge.py's tolerance of stray serial lines.
    """
    if cmd.startswith("MOVE "):
        parts = cmd.split()
        try:
            target_mm = float(parts[parts.index("X") + 1])
        except (ValueError, IndexError):
            print(f"[WARN] bad MOVE line: {cmd!r}")
            return
        _move_to(target_mm)
        return
    handler = _box3_routes.get(cmd)
    if handler is not None:
        handler()


def _push_box3_line(line):
    """Write one newline-terminated line back to the BOX3 if connected."""
    with _box3_lock:
        port = _box3_serial
        if port is None:
            return
        try:
            port.write((line + "\n").encode("ascii"))
        except serial.SerialException:
            pass  # link drop is handled by the read loop's reconnect


def _publish_pos_loop():
    """Push POS:<mm> to the BOX3 and refresh the /status cache.

    During a blocking move the command thread holds _rail_lock, so a
    non-blocking acquire is used: if the lock is busy the cached
    position is published instead of stalling the reader.
    """
    while True:
        time.sleep(pos_push_interval_s)
        with _state_lock:
            moving = _state["state"] == "moving"
            cached_mm = _state["position_mm"]
        if not moving and _rail_lock.acquire(blocking=False):
            try:
                pos = _rail.read_position_mm() if _rail is not None else None
            finally:
                _rail_lock.release()
            if pos is None:
                _set_state(state="error", connected=False)
            else:
                _set_state(position_mm=pos, state="idle", connected=True)
                cached_mm = pos
        if cached_mm is not None:
            _push_box3_line(f"POS:{cached_mm:.3f}")


def _open_box3():
    """Open the BOX3 CDC serial, retrying until it succeeds.

    A finite timeout makes readline() wake periodically so the loop can
    react to shutdown and a silent link does not block forever.
    """
    while True:
        try:
            return serial.Serial(
                port=box3_serial_port,
                baudrate=box3_baud,
                timeout=box3_serial_timeout_s,
            )
        except serial.SerialException as exc:
            print(
                f"[BOX3] open {box3_serial_port} failed: {exc} "
                f"-- retry in {reconnect_delay_s}s"
            )
            time.sleep(reconnect_delay_s)


def _probe_rail_port():
    """Return the first /dev/ttyUSB* whose MINAS model-name read answers.

    Mirrors claude_test/probe_ports.py: the rail is located by probing
    rather than assuming a fixed path (LP 5).
    """
    for port in sorted(glob.glob(rail_port_glob)):
        try:
            probe = LinearMotorController(port)
            probe.ser.timeout = 0.5
            model = probe.read_model_name()
            probe.ser.close()
        except (serial.SerialException, OSError):
            continue
        if model:
            return port
    return None


def make_app():
    """Build the FastAPI app (imported lazily so the core module and its
    offline tests do not require fastapi/pydantic)."""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field

    app = FastAPI(
        title="Linear rail bridge",
        version="1.0",
        description="Status/control plane mirroring the CMD:* protocol "
        "used by the ESP32-S3-BOX-3 touch UI.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class MoveRequest(BaseModel):
        target_mm: float = Field(
            ...,
            ge=rail_min_mm,
            le=rail_max_mm,
            description="Absolute target in mm",
        )

    @app.get("/status")
    def http_status():
        with _state_lock:
            return dict(_state)

    @app.post("/move")
    def http_move(req: MoveRequest):
        _move_to(req.target_mm)
        with _state_lock:
            if _state["state"] == "error":
                raise HTTPException(503, "rail RS485 failure")
            return dict(_state)

    @app.post("/jog/{direction}")
    def http_jog(direction: str):
        steps = {"positive": jog_step_mm, "negative": -jog_step_mm}
        if direction not in steps:
            raise HTTPException(400, f"unknown direction: {direction}")
        _jog(steps[direction])
        with _state_lock:
            return dict(_state)

    @app.post("/home")
    def http_home():
        _home()
        with _state_lock:
            return dict(_state)

    return app


def run_http_server():
    """Serve the status/control API from a background daemon thread.

    install_signal_handlers is patched away because uvicorn can only
    register signal handlers from the main thread.
    """
    import asyncio

    import uvicorn

    config = uvicorn.Config(
        make_app(), host="0.0.0.0", port=http_port, log_level="warning"
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    asyncio.run(server.serve())


def main():
    """Open the rail, start the feedback + HTTP threads, run the loop."""
    global _rail, _box3_serial

    port = rail_port or _probe_rail_port()
    if port is None:
        print("[RAIL] no MINAS amp found on any /dev/ttyUSB* port")
        sys.exit(1)
    print(f"[RAIL] using {port}")
    _rail = LinearMotorController(port)

    initial = _rail.read_position_mm()
    _set_state(
        position_mm=initial,
        connected=initial is not None,
        state="idle" if initial is not None else "error",
    )

    threading.Thread(target=_publish_pos_loop, daemon=True).start()
    threading.Thread(target=run_http_server, daemon=True).start()
    print(f"[HTTP] status/control on http://0.0.0.0:{http_port} (/status)")

    try:
        while True:
            print(f"[BOX3] opening {box3_serial_port} ...")
            port_serial = _open_box3()
            with _box3_lock:
                _box3_serial = port_serial
            print("[BOX3] connected. Touch the display to drive the rail.")
            try:
                while True:
                    raw = port_serial.readline()
                    if not raw:
                        continue  # idle read timeout; keep waiting
                    line = raw.decode("ascii", errors="ignore").strip()
                    if not line.startswith("CMD:"):
                        continue
                    cmd = line[len("CMD:") :]
                    print(f"[CMD] {cmd}")
                    box3_dispatch(cmd)
            except serial.SerialException as exc:
                print(f"[BOX3] serial error: {exc}")
            finally:
                with _box3_lock:
                    _box3_serial = None
                try:
                    port_serial.close()
                except serial.SerialException:
                    pass
            print(f"[BOX3] disconnected, reconnecting in {reconnect_delay_s}s")
            time.sleep(reconnect_delay_s)
    except KeyboardInterrupt:
        print("\n[BOX3] stopping.")
    finally:
        if _rail is not None:
            _rail.ser.close()
        print("[RAIL] closed.")


if __name__ == "__main__":
    main()
