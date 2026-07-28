"""FastAPI server for monitoring and controlling the linear rail.

The server exposes the MINAS A6 linear rail over HTTP on port 17052 so a
remote client (for example an ESP32-S3) or a web browser can read live
position and drive jog / absolute moves / home.

:class:`LinearMotorController` is synchronous and blocking and handles
one RS485 command at a time. To keep that serial port safe under
concurrent HTTP requests, a single background poller thread owns every
read and refreshes an immutable snapshot; GET handlers return that
cached snapshot without touching the port, and control handlers take the
same lock the poller uses. See :class:`RailMonitor`.

This mirrors the sibling HotplateController's ``hotplate_controller.server``
(same DeviceMonitor + FastAPI + ESP32-client shape); only the device link
differs (RS485 / MINAS here vs USB-CDC there).

Run it with::

    python3 server.py [PORT]

where ``PORT`` is the rail's serial device path; it defaults to
auto-detection by probing /dev/ttyUSB* and then ``$RAIL_PORT``.
"""

import glob
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from html import escape
from typing import Optional

import serial
import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from LinearMotorController import LinearMotorController

# Bind on all interfaces so an ESP32 on the same network can reach the
# server; the port is the admin-assigned dedicated REST port.
server_host = "0.0.0.0"
server_port = 17052

# How often the background thread reads the device, in seconds.
poll_interval_s = 0.5

# Soft travel limits enforced here -- LinearMotorController has none.
# CALIBRATE to the physical rail before unsupervised motion.
rail_min_mm = 0.0
rail_max_mm = 190.0

# Continuous jog (CMD jog/start..jog/stop): drive Pr3.04 at this speed.
jog_speed = 25  # r/min; low speed keeps deceleration overshoot small
jog_watch_interval_s = 0.1  # position-poll cadence while jogging
# Safety: auto-stop a held jog after this long, so a dropped jog/stop
# over WiFi can never leave the rail running indefinitely.
jog_max_duration_s = 30.0

# Absolute move (move_to_mm) and home settings.
move_tolerance_mm = 0.1
move_max_iterations = 5
move_timeout_per_step_s = 10.0
home_target_mm = 0.0

# Auto-probe pattern for the rail's RS485-over-USB port.
rail_port_glob = "/dev/ttyUSB*"


class RailRangeError(ValueError):
    """A requested target is outside the soft travel envelope."""


class RailCommError(RuntimeError):
    """The rail is unavailable (RS485 failure or not initialized)."""


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string (seconds)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def probe_rail_port() -> Optional[str]:
    """Return the first /dev/ttyUSB* whose MINAS model read answers."""
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


def resolve_port(explicit: Optional[str] = None) -> Optional[str]:
    """Decide which serial port to open.

    An explicit value wins, otherwise auto-probe /dev/ttyUSB*, otherwise
    ``$RAIL_PORT``.

    Args:
        explicit: A port path supplied on the command line, or ``None``.

    Returns:
        The chosen port path, or ``None`` if nothing could be resolved.
    """
    if explicit:
        return explicit
    return probe_rail_port() or os.environ.get("RAIL_PORT")


class RailMonitor:
    """Own a :class:`LinearMotorController` and serialize all access.

    A background thread polls the position every ``poll_interval`` seconds
    and stores the result in an immutable snapshot dict. Reads of the
    snapshot are lock-free because the reference is replaced atomically;
    every call that touches the serial port -- the poller and all control
    methods -- holds ``self._lock`` so commands never interleave.

    Continuous jog runs on its own thread (``_jog_loop``) so the HTTP
    request that started it returns immediately and a later jog/stop is
    free to arrive; the loop watches the soft limit and a maximum
    duration, and always returns Pr3.04 to 0 in its ``finally``.
    """

    def __init__(
        self,
        controller: LinearMotorController,
        poll_interval: float = poll_interval_s,
    ):
        """Wrap ``controller`` without starting the poller yet."""
        self._controller = controller
        self._poll_interval = poll_interval
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_poll_monotonic = time.monotonic()
        self._snapshot = self._disconnected_snapshot("no reading yet")
        self._jog_lock = threading.Lock()
        self._jog_active = False
        self._jog_thread: Optional[threading.Thread] = None

    # -- snapshot ---------------------------------------------------

    @staticmethod
    def _disconnected_snapshot(error: str) -> dict:
        """Build a snapshot with no reading and an error message."""
        return {
            "connected": False,
            "position_mm": None,
            "target_mm": None,
            "state": "error",
            "timestamp": utc_now_iso(),
            "error": error,
        }

    def _set_state(self, **fields) -> None:
        """Merge ``fields`` into the snapshot, replacing it atomically."""
        snapshot = dict(self._snapshot)
        snapshot.update(fields)
        snapshot["timestamp"] = utc_now_iso()
        self._snapshot = snapshot

    def poll_once(self) -> dict:
        """Read the position once and refresh the snapshot.

        Skips the read while a jog owns the port (the jog loop updates the
        position itself) and uses a non-blocking lock so an in-progress
        blocking move never stalls the poller.

        Returns:
            The current snapshot dict.
        """
        with self._jog_lock:
            jogging = self._jog_active
        if jogging:
            return self._snapshot
        if self._lock.acquire(blocking=False):
            try:
                pos = self._controller.read_position_mm()
            finally:
                self._lock.release()
            if pos is None:
                self._set_state(
                    connected=False, state="error", error="read failed"
                )
            else:
                self._set_state(
                    connected=True,
                    position_mm=pos,
                    state="idle",
                    error=None,
                )
            self._last_poll_monotonic = time.monotonic()
        return self._snapshot

    @property
    def snapshot(self) -> dict:
        """The most recent snapshot dict (replaced atomically)."""
        return self._snapshot

    def current_status(self) -> dict:
        """Return the snapshot plus the age of its reading in seconds."""
        snapshot = self._snapshot
        age = round(time.monotonic() - self._last_poll_monotonic, 2)
        return {**snapshot, "age_seconds": age}

    # -- background poller -----------------------------------------

    def start(self) -> None:
        """Start the background polling thread if it is not running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="rail-poller", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        """Poll forever until stopped, surviving unexpected errors."""
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception:
                # Last-resort guard so the poller thread never dies.
                pass
            self._stop_event.wait(self._poll_interval)

    def stop(self) -> None:
        """Signal the poller to stop and wait for it to finish."""
        self.jog_stop()
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval + 1.0)

    # -- control (serialized) --------------------------------------

    def _within_limits(self, target_mm: float) -> bool:
        """Return whether ``target_mm`` is inside the soft envelope."""
        return rail_min_mm <= target_mm <= rail_max_mm

    def move(self, target_mm: float) -> dict:
        """Move to an absolute target in mm, refusing out-of-limit moves."""
        if not self._within_limits(target_mm):
            raise RailRangeError(
                f"{target_mm} mm outside [{rail_min_mm}, {rail_max_mm}]"
            )
        self._set_state(state="moving", target_mm=target_mm)
        with self._lock:
            result = self._controller.move_to_mm(
                target_mm,
                tolerance_mm=move_tolerance_mm,
                max_iterations=move_max_iterations,
                timeout_per_step=move_timeout_per_step_s,
            )
        if result is None:
            self._set_state(connected=False, state="error", error="move failed")
        elif not result.converged:
            # The amp answered, so the link is fine and the position is
            # real -- the rail simply never reached the target. Record
            # where it actually stopped and surface it as an error rather
            # than reporting the move done at the wrong place.
            self._set_state(
                connected=True,
                position_mm=result.position_mm,
                state="error",
                error=(
                    f"move to {target_mm} mm did not converge"
                    f" ({result.reason}); stopped at {result.position_mm} mm"
                ),
            )
        else:
            self._set_state(
                connected=True,
                position_mm=result.position_mm,
                state="idle",
                error=None,
            )
        return self.current_status()

    def home(self) -> dict:
        """Return the rail to the power-on origin (0 mm)."""
        return self.move(home_target_mm)

    def jog_start(self, direction: int) -> None:
        """Begin a continuous velocity jog in ``direction`` (+1 / -1)."""
        with self._jog_lock:
            if self._jog_active:
                return
            base = self._snapshot.get("position_mm")
            if base is None:
                raise RailCommError("current position unknown")
            if direction > 0 and base >= rail_max_mm:
                raise RailRangeError(f"already at upper limit {rail_max_mm}")
            if direction < 0 and base <= rail_min_mm:
                raise RailRangeError(f"already at lower limit {rail_min_mm}")
            self._jog_active = True
            self._jog_thread = threading.Thread(
                target=self._jog_loop, args=(direction,), daemon=True
            )
            self._jog_thread.start()

    def jog_stop(self) -> None:
        """Signal the continuous jog thread to stop."""
        with self._jog_lock:
            self._jog_active = False

    def _jog_loop(self, direction: int) -> None:
        """Hold a continuous speed command while watching the limits.

        Stops on jog_stop, at the soft limit, after ``jog_max_duration_s``
        (dropped-stop safety), or on an RS485 read failure. Pr3.04 is
        always returned to 0 in the finally.
        """
        speed = direction * jog_speed
        with self._lock:
            acquired = self._controller._acquire_execution_rights()
            if acquired:
                self._controller._write_parameter(3, 4, speed)
        if not acquired:
            with self._jog_lock:
                self._jog_active = False
            self._set_state(connected=False, state="error", error="exec rights")
            return
        self._set_state(state="moving", target_mm=None)
        deadline = time.monotonic() + jog_max_duration_s
        try:
            while True:
                with self._jog_lock:
                    if not self._jog_active:
                        break
                if time.monotonic() >= deadline:
                    break  # safety auto-stop
                time.sleep(jog_watch_interval_s)
                with self._lock:
                    pos = self._controller.read_position_mm()
                if pos is None:
                    self._set_state(
                        connected=False, state="error", error="read failed"
                    )
                    break
                self._set_state(connected=True, position_mm=pos)
                if direction > 0 and pos >= rail_max_mm:
                    break
                if direction < 0 and pos <= rail_min_mm:
                    break
        finally:
            with self._lock:
                self._controller._write_parameter(3, 4, 0)
                self._controller._release_execution_rights()
                final = self._controller.read_position_mm()
            if final is not None:
                self._set_state(
                    connected=True,
                    position_mm=final,
                    state="idle",
                    error=None,
                )
            else:
                self._set_state(state="idle")
            with self._jog_lock:
                self._jog_active = False


class TargetValue(BaseModel):
    """Request body for an absolute move command."""

    value: float


def get_monitor(request: Request) -> RailMonitor:
    """Return the app's :class:`RailMonitor` or fail with 503."""
    monitor = getattr(request.app.state, "monitor", None)
    if monitor is None:
        raise RailCommError("rail monitor is not initialized")
    return monitor


def render_dashboard(status: dict) -> str:
    """Render the monitoring snapshot as a self-refreshing HTML page."""

    def cell(value, suffix=""):
        if value is None:
            return "--"
        return f"{value}{suffix}"

    connected = "yes" if status["connected"] else "no"
    error = status.get("error")
    error_row = ""
    if error:
        error_row = f"<p class='err'>error: {escape(str(error))}</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="2">
  <title>Linear rail monitor</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    h1 {{ font-size: 1.3rem; }}
    table {{ border-collapse: collapse; }}
    td {{ padding: 0.3rem 1rem; border-bottom: 1px solid #ddd; }}
    .label {{ color: #555; }}
    .val {{ font-weight: 600; font-variant-numeric: tabular-nums; }}
    .err {{ color: #b00; }}
  </style>
</head>
<body>
  <h1>Linear rail monitor</h1>
  <table>
    <tr><td class="label">connected</td>
        <td class="val">{connected}</td></tr>
    <tr><td class="label">position</td>
        <td class="val">{cell(status["position_mm"], " mm")}</td></tr>
    <tr><td class="label">target</td>
        <td class="val">{cell(status["target_mm"], " mm")}</td></tr>
    <tr><td class="label">state</td>
        <td class="val">{escape(str(status["state"]))}</td></tr>
  </table>
  {error_row}
  <p class="label">updated {escape(status["timestamp"])}
     (age {status.get("age_seconds", "?")} s)</p>
</body>
</html>"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the rail on startup and close it on shutdown.

    If a monitor was injected onto ``app.state`` (the tests do this), it
    is used as-is and no real serial device is opened.
    """
    monitor = getattr(app.state, "monitor", None)
    controller: Optional[LinearMotorController] = None
    if monitor is None:
        port = resolve_port(getattr(app.state, "port", None))
        if not port:
            raise RuntimeError("no rail found; pass a port or set $RAIL_PORT")
        controller = LinearMotorController(port)
        monitor = RailMonitor(controller)
        app.state.monitor = monitor
    monitor.start()
    try:
        yield
    finally:
        monitor.stop()
        if controller is not None:
            controller.ser.close()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Linear rail monitor",
        description="Monitor and control a MINAS A6 linear rail.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(RailRangeError)
    async def _range_error(request: Request, exc: RailRangeError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(RailCommError)
    async def _comm_error(request: Request, exc: RailCommError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(monitor: RailMonitor = Depends(get_monitor)):
        """Serve the self-refreshing HTML monitoring dashboard."""
        return render_dashboard(monitor.current_status())

    @app.get("/health")
    async def health(monitor: RailMonitor = Depends(get_monitor)):
        """Report server liveness and rail connection state."""
        return {"status": "ok", "connected": monitor.snapshot["connected"]}

    @app.get("/status")
    async def status(monitor: RailMonitor = Depends(get_monitor)):
        """Return the full latest snapshot plus its reading age."""
        return monitor.current_status()

    @app.post("/control/move")
    def control_move(
        body: TargetValue,
        monitor: RailMonitor = Depends(get_monitor),
    ):
        """Move to an absolute target position in mm."""
        return monitor.move(body.value)

    @app.post("/control/jog/start/{direction}")
    def control_jog_start(
        direction: str,
        monitor: RailMonitor = Depends(get_monitor),
    ):
        """Begin a continuous jog (``positive`` or ``negative``)."""
        signs = {"positive": 1, "negative": -1}
        if direction not in signs:
            raise RailRangeError(f"unknown direction: {direction}")
        monitor.jog_start(signs[direction])
        return {"ok": True}

    @app.post("/control/jog/stop")
    def control_jog_stop(monitor: RailMonitor = Depends(get_monitor)):
        """Stop the continuous jog."""
        monitor.jog_stop()
        return {"ok": True}

    @app.post("/control/home")
    def control_home(monitor: RailMonitor = Depends(get_monitor)):
        """Return the rail to the power-on origin (0 mm)."""
        return monitor.home()

    return app


app = create_app()


def main(argv: Optional[list] = None) -> int:
    """Resolve the serial port and run the server with uvicorn.

    Args:
        argv: Argument list to parse; defaults to ``sys.argv``.

    Returns:
        A process exit code (``0`` on a clean run, ``1`` if no rail
        could be resolved).
    """
    argv = sys.argv if argv is None else argv
    explicit = argv[1] if len(argv) > 1 else None
    port = resolve_port(explicit)
    if not port:
        print("no rail found (set PORT arg or $RAIL_PORT).")
        return 1
    app.state.port = port
    print(
        f"serving linear rail on http://{server_host}:{server_port} "
        f"(device {port}) ..."
    )
    uvicorn.run(app, host=server_host, port=server_port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
