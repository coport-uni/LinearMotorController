# ESP32-S3 client for the linear rail server

An ESP-IDF firmware for the **ESP32-S3-BOX-3** that connects to the
LinearMotorController FastAPI server (see
[`../../docs/server_api.md`](../../docs/server_api.md)) over WiFi and drives
the rail from the touchscreen. **No USB link to the NUC is needed at
runtime — only power.** USB is used once, to flash.

It reuses the request/response and LVGL structure of the sibling
`HotplateController` `external/ESP32S3/` client (WiFi STA in `network.c`,
an `esp_http_client` command-queue + single client task in
`rail_client.c`). The touch UI is a faithful port of the existing
`ESP32S3BOX3MotorController` UI so the rail integrates into the controller
the lab already uses.

## What it does

- **On first boot (no stored WiFi): on-device provisioning.** The screen
  shows a list of nearby networks and an on-screen keyboard. Pick the
  2.4 GHz SSID (the ESP32-S3 is 2.4 GHz only), type the password, press
  OK. Credentials are saved to NVS and reused automatically on later
  boots. To change networks, **long-press the on-board CONFIG button** —
  it clears the saved credentials and reboots into provisioning.
- **Once connected: the control UI** (a 3-tab port of the existing BOX-3
  UI). It polls `GET /status` every `RAIL_POLL_INTERVAL_S` seconds.
  - **Jog Control** (default tab): the **Y buttons drive the rail** —
    hold to jog continuously (`POST /control/jog/start/{positive,negative}`
    on press, `/control/jog/stop` on release), and the centre **Home**
    button homes it (`POST /control/home`). The X/Z quadrant dial is a
    placeholder for the future pipette-station motors (no backend yet).
  - **Move Control**: an X/Z target picker, also a pipette-station
    placeholder.
  - **Status**: WiFi (state / SSID / IP / RSSI / MAC) and the rail server
    state, position, and reading age.

All HTTP runs on one background task, so requests never overlap.

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
cd controller/ESP32S3
idf.py set-target esp32s3
idf.py menuconfig    # -> "Rail monitor"
```

Set, under **Rail monitor**:

| Option | Meaning |
|--------|---------|
| `RAIL_SERVER_URL` | Base URL of the server, e.g. `http://192.168.1.129:17052` (the NUC's LAN IP and the dedicated REST port). |
| `RAIL_POLL_INTERVAL_S` | Status poll period (seconds). |
| `RAIL_WIFI_SSID` / `RAIL_WIFI_PASSWORD` | Optional. Leave empty (default) to use on-device provisioning. Set them only to skip provisioning with a fixed network. |

> The server URL must be the NUC host's **LAN IP**, not a container IP.
> When the server runs in a Docker container, the host must publish
> `:17052` to the LAN (as it does for ssh).

## Build, flash, monitor

```bash
idf.py build
idf.py -p /dev/ttyACM0 flash monitor   # use your board's port
```

Reflashing with `idf.py flash` does not erase NVS, so stored WiFi
credentials survive a firmware update.

## Files

| File | Role |
|------|------|
| `main/main.c` | App entry: BSP/LVGL init; provision when uncredentialed, else run; CONFIG long-press re-provisions. |
| `main/network.c/.h` | WiFi STA, NVS credential storage, scan, status getters. |
| `main/prov_ui.c/.h` | LVGL provisioning screen (network list + keyboard). |
| `main/rail_client.c/.h` | HTTP polling + control task, JSON parsing. |
| `main/ui.c/.h` | Ported 3-tab control UI (Move / Jog / Status). |
| `main/buttons_check.c/.h` | On-board CONFIG / MUTE buttons. |
| `main/Kconfig.projbuild` | `menuconfig` options. |
| `sdkconfig.defaults` | Board defaults (ESP32-S3, PSRAM, LVGL, fonts). |

## Notes

- Jog is **continuous**: hold a Y button to move, release to stop. The
  server also stops the jog at a soft travel limit or after a maximum
  duration, so a dropped `stop` over WiFi cannot leave the rail running.
- Out-of-range / refused commands are answered by the server with HTTP
  422; the client logs the status code.
- The endpoint contract this firmware depends on is documented in
  [`../../docs/server_api.md`](../../docs/server_api.md).
