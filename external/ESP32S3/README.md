# ESP32-S3 client for the linear rail server

An ESP-IDF firmware for the **ESP32-S3-BOX-3** that connects to the
LinearMotorController FastAPI server (see
[`../../docs/server_api.md`](../../docs/server_api.md)) over WiFi, shows
the rail's position on the LCD, and jogs / homes it from the touchscreen.
**No USB link to the NUC is needed at runtime — only power.**

It mirrors the sibling `HotplateController` `external/ESP32S3/` client:
the WiFi bring-up (`network.c`), the `esp_http_client` request/response
pattern, the LVGL display, the on-board buttons, and the
command-queue + single client task all follow the same structure. Only
the device differs (a rail driven over RS485 vs a hotplate over USB).

## What it does

- Polls `GET /status` every `RAIL_POLL_INTERVAL_S` seconds and shows:
  - rail position (mm), the current target, and the run state,
  - rail connection state (online / offline) and reading age.
- Sends control commands via the touch buttons:
  - **Jog −/+** — *hold to jog continuously* (`POST /control/jog/start/
    {negative,positive}` on press, `POST /control/jog/stop` on release),
  - **Home** — return to the origin (`POST /control/home`).
- The on-board CONFIG button also homes the rail, so the demo works
  without the touchscreen.

All HTTP runs on one background task, so requests never overlap. Touch
callbacks only enqueue a command; the task performs the request and then
refreshes the readings.

## Hardware

- **ESP32-S3-BOX-3** (320x240 LCD with capacitive touch, two buttons).
- The rail server reachable on the same WiFi network. The rail itself
  stays wired to the NUC over USB-RS485 — the ESP32 never touches RS485.

## Prerequisites

- [ESP-IDF](https://docs.espressif.com/projects/esp-idf/) **>= 5.3**
  installed and exported (`. $IDF_PATH/export.sh`).
- The managed components (`espressif/esp-box-3`, `espressif/cjson`) are
  pulled automatically by the component manager on first build.

## Configure

```bash
cd external/ESP32S3
idf.py set-target esp32s3
idf.py menuconfig    # -> "Rail monitor"
```

Set, under **Rail monitor**:

| Option | Meaning |
|--------|---------|
| `RAIL_WIFI_SSID` / `RAIL_WIFI_PASSWORD` | WiFi (WPA2-Personal). |
| `RAIL_SERVER_URL` | Base URL of the server, e.g. `http://192.168.1.16:17052`. |
| `RAIL_POLL_INTERVAL_S` | Status poll period (seconds). |

Leaving the SSID empty boots the UI in a "configure WiFi" state without
attempting to connect.

## Build, flash, monitor

```bash
idf.py build
idf.py -p /dev/ttyACM0 flash monitor   # use your board's port
```

On boot the screen shows `starting`, then `WiFi connecting...`, then the
live position once the server responds. Hold **Jog −/+** to move the rail
and tap **Home** to return to the origin.

## Files

| File | Role |
|------|------|
| `main/main.c` | App entry: BSP/LVGL init, wiring, task startup. |
| `main/network.c/.h` | WiFi STA bring-up and connection state. |
| `main/rail_client.c/.h` | HTTP polling + control task, JSON parsing. |
| `main/ui.c/.h` | LVGL readings panel and jog/home buttons. |
| `main/buttons_check.c/.h` | On-board CONFIG / MUTE button handling. |
| `main/Kconfig.projbuild` | `menuconfig` options. |
| `sdkconfig.defaults` | Board defaults (ESP32-S3, PSRAM, LVGL). |

## Notes

- Jog is **continuous**: hold a Jog button to move, release to stop. The
  server also stops the jog at a soft travel limit or after a maximum
  duration, so a dropped `stop` over WiFi cannot leave the rail running.
- Out-of-range / refused commands are answered by the server with HTTP
  422; the client logs the status code.
- The endpoint contract this firmware depends on is documented in
  [`../../docs/server_api.md`](../../docs/server_api.md).
