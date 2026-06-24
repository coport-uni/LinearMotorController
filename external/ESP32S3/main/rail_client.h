#pragma once

#include <stdbool.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Control actions the UI can request. Jog is continuous: the UI enqueues
 * RAIL_CMD_JOG_START on button press and RAIL_CMD_JOG_STOP on release, so
 * holding a jog button moves the rail until released (a server-side soft
 * limit or maximum duration also stops it).
 */
typedef enum {
    RAIL_CMD_JOG_START,   /* arg: +1 = positive (forward), -1 = negative */
    RAIL_CMD_JOG_STOP,
    RAIL_CMD_HOME,
} rail_cmd_type_t;

typedef struct {
    rail_cmd_type_t type;
    float           arg;
} rail_command_t;

/**
 * @brief  Start the background client task.
 *
 * Creates the command queue and a task that polls `GET /status` every
 * CONFIG_RAIL_POLL_INTERVAL_S seconds, pushes readings to the UI, and
 * drains queued control commands as `POST /control/...` requests. All
 * HTTP runs on this one task, so requests never overlap.
 *
 * @return ESP_OK on success, or an esp_err_t on allocation failure.
 */
esp_err_t rail_client_init(void);

/**
 * @brief  Queue a control command for the client task to send.
 *
 * Non-blocking and safe to call from the LVGL/UI task; the actual HTTP
 * request happens later on the client task.
 *
 * @param  cmd  Command to enqueue (copied).
 * @return true if queued, false if the queue is full or uninitialized.
 */
bool      rail_client_enqueue(const rail_command_t *cmd);

#ifdef __cplusplus
}
#endif
