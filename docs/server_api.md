# Linear rail control server — HTTP API

A small FastAPI server that exposes the MINAS A6 linear rail's position
over HTTP and lets a client drive jog / absolute moves / home. It is
meant to be consumed by an ESP32 (or any HTTP client) and also serves a
self-refreshing web dashboard. It mirrors the sibling
`HotplateController` server; only the device link differs (RS485 / MINAS
here vs USB-CDC there).

## Design in one paragraph

The device wrapper (`LinearMotorController`) talks to the rail over a
blocking RS485 serial port and handles one command at a time. The server
runs a single **background poller thread** that reads the position about
twice a second and stores the result in an in-memory snapshot. `GET`
endpoints return that cached snapshot, so they are fast and never block
on the serial port. `POST` control endpoints take the same lock the
poller uses, so a write never interleaves with a read. Readings are at
most ~0.5 s old (see `age_seconds` in `/status`).

## Running the server

```bash
pip install -r requirements.txt
python3 server.py [PORT]
```

- `PORT` is the serial device path (e.g. `/dev/ttyUSB4`). If omitted, the
  server auto-detects by probing `/dev/ttyUSB*` with a MINAS model read,
  then falls back to the `$RAIL_PORT` environment variable.
- The server listens on `0.0.0.0:17052`, so a device on the same network
  can reach it at `http://<server-ip>:17052`.
- Interactive API docs (Swagger UI) are at `/docs`; ReDoc is at `/redoc`.

Base URL used in the examples below: `http://localhost:17052`.

## Endpoints

### Monitoring (GET)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Self-refreshing HTML dashboard (for a browser). |
| GET | `/health` | Liveness and rail connection state. |
| GET | `/status` | Full snapshot (position, target, state) plus its age. |

`GET /status` response:

```json
{
  "connected": true,
  "position_mm": 45.123,
  "target_mm": null,
  "state": "idle",
  "timestamp": "2026-06-23T09:05:26+00:00",
  "error": null,
  "age_seconds": 0.4
}
```

When the rail is absent or unreadable, the server stays up and returns
`"connected": false`, `"position_mm": null`, `"state": "error"`, and a
human-readable `"error"` string. Always check `connected` (and
`age_seconds`) before trusting a value. `state` is one of `idle`,
`moving`, or `error`.

### Control (POST)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/control/move` | `{"value": <mm>}` | Move to an absolute target (soft-limited to `[0, 190]` mm). |
| POST | `/control/jog/start/{direction}` | — | Start a continuous jog; `direction` is `positive` or `negative`. |
| POST | `/control/jog/stop` | — | Stop the continuous jog. |
| POST | `/control/home` | — | Return the rail to the power-on origin (0 mm). |

`/control/move` and `/control/home` are **blocking** (they return when
the closed-loop move settles) and respond with the full `/status`
snapshot. `/control/jog/start/*` returns immediately with `{"ok": true}`
and the jog runs until `/control/jog/stop`, a soft limit, or a
server-side maximum duration (a dropped `stop` over WiFi can never leave
the rail running). `/control/jog/stop` returns `{"ok": true}`.

### Status codes

| Code | Meaning |
|------|---------|
| 200 | Success. |
| 422 | Target out of range, unknown jog direction, or malformed body. |
| 503 | The rail monitor is not ready or the serial exchange failed. |

## curl examples

```bash
# Read everything
curl http://localhost:17052/status

# Move to an absolute 50 mm
curl -X POST http://localhost:17052/control/move \
     -H 'Content-Type: application/json' -d '{"value": 50}'

# Start, then stop a positive jog
curl -X POST http://localhost:17052/control/jog/start/positive
curl -X POST http://localhost:17052/control/jog/stop

# Home
curl -X POST http://localhost:17052/control/home

# Out-of-range move -> 422
curl -i -X POST http://localhost:17052/control/move \
     -H 'Content-Type: application/json' -d '{"value": 999}'
```

## ESP32 example (Arduino `HTTPClient`)

Reading the status and jogging the rail from an ESP32. Replace the Wi-Fi
credentials and the server IP with your own.

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "your-ssid";
const char* WIFI_PASS = "your-password";
const char* SERVER = "http://192.168.1.16:17052";  // server IP:port

// GET /status and print the raw JSON.
void readStatus() {
  HTTPClient http;
  http.begin(String(SERVER) + "/status");
  int code = http.GET();
  if (code == 200) {
    Serial.println(http.getString());
  } else {
    Serial.printf("GET /status failed: %d\n", code);
  }
  http.end();
}

// POST a control command with no body (e.g. jog start/stop, home).
void post(const char* path) {
  HTTPClient http;
  http.begin(String(SERVER) + path);
  int code = http.POST("");
  Serial.printf("POST %s -> %d\n", path, code);
  http.end();
}

void loop() {
  readStatus();
  post("/control/jog/start/positive");
  delay(500);
  post("/control/jog/stop");
  delay(2000);
}
```

The production ESP-BOX-3 firmware lives under
[`external/ESP32S3/`](../external/ESP32S3/) and uses `esp_http_client` +
`cJSON` with a command queue (mirroring HotplateController's
`hotplate_client.c`); the Arduino sketch above is just a minimal
illustration.
