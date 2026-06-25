#include "rail_client.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include "esp_log.h"
#include "esp_http_client.h"
#include "cJSON.h"

#include "sdkconfig.h"

#include "network.h"
#include "ui.h"

static const char *TAG = "rail";

#define BUF_INITIAL       1024
#define BUF_MAX           (16 * 1024)
#define HTTP_TIMEOUT_MS   6000
#define CMD_QUEUE_LEN     8

static QueueHandle_t s_cmd_queue;

/* ---------------------- HTTP response buffer ---------------------- */

typedef struct {
    char  *buf;
    size_t len;
    size_t cap;
} resp_buf_t;

static esp_err_t buf_ensure(resp_buf_t *r, size_t need)
{
    if (r->cap >= need) {
        return ESP_OK;
    }
    size_t new_cap = r->cap ? r->cap : BUF_INITIAL;
    while (new_cap < need) {
        new_cap *= 2;
        if (new_cap > BUF_MAX) {
            new_cap = BUF_MAX;
            break;
        }
    }
    if (new_cap < need) {
        return ESP_ERR_NO_MEM;
    }
    char *n = realloc(r->buf, new_cap);
    if (!n) {
        return ESP_ERR_NO_MEM;
    }
    r->buf = n;
    r->cap = new_cap;
    return ESP_OK;
}

static esp_err_t http_event(esp_http_client_event_t *evt)
{
    if (evt->event_id != HTTP_EVENT_ON_DATA || evt->data_len <= 0) {
        return ESP_OK;
    }
    resp_buf_t *r = (resp_buf_t *)evt->user_data;
    if (!r) {
        return ESP_OK;
    }
    if (buf_ensure(r, r->len + (size_t)evt->data_len + 1) != ESP_OK) {
        ESP_LOGW(TAG, "response buffer hit cap %d", BUF_MAX);
        return ESP_OK;
    }
    memcpy(r->buf + r->len, evt->data, evt->data_len);
    r->len += (size_t)evt->data_len;
    r->buf[r->len] = '\0';
    return ESP_OK;
}

static void buf_free(resp_buf_t *r)
{
    free(r->buf);
    r->buf = NULL;
    r->len = 0;
    r->cap = 0;
}

/* ---------------------- URL + requests ---------------------- */

static void make_url(char *out, size_t out_len, const char *path)
{
    const char *base = CONFIG_RAIL_SERVER_URL;
    size_t bl = strlen(base);
    while (bl > 0 && base[bl - 1] == '/') {  /* trim trailing slash */
        bl--;
    }
    snprintf(out, out_len, "%.*s%s", (int)bl, base, path);
}

static esp_err_t http_get(const char *path, resp_buf_t *resp, int *status_out)
{
    char url[256];
    make_url(url, sizeof(url), path);
    esp_http_client_config_t cfg = {
        .url           = url,
        .method        = HTTP_METHOD_GET,
        .timeout_ms    = HTTP_TIMEOUT_MS,
        .event_handler = http_event,
        .user_data     = resp,
    };
    esp_http_client_handle_t cli = esp_http_client_init(&cfg);
    if (!cli) {
        return ESP_FAIL;
    }
    esp_err_t err = esp_http_client_perform(cli);
    *status_out = esp_http_client_get_status_code(cli);
    esp_http_client_cleanup(cli);
    return err;
}

static esp_err_t http_post(const char *path, const char *body,
                           int *status_out)
{
    char url[256];
    make_url(url, sizeof(url), path);
    esp_http_client_config_t cfg = {
        .url        = url,
        .method     = HTTP_METHOD_POST,
        .timeout_ms = HTTP_TIMEOUT_MS,
    };
    esp_http_client_handle_t cli = esp_http_client_init(&cfg);
    if (!cli) {
        return ESP_FAIL;
    }
    if (body) {
        esp_http_client_set_header(cli, "Content-Type", "application/json");
        esp_http_client_set_post_field(cli, body, strlen(body));
    }
    esp_err_t err = esp_http_client_perform(cli);
    *status_out = esp_http_client_get_status_code(cli);
    esp_http_client_cleanup(cli);
    return err;
}

/* ---------------------- Status polling ---------------------- */

/* Read a JSON number into *out; returns false (and leaves *out alone) if
 * the key is missing or null -- matches the server returning null fields
 * while the rail is disconnected. */
static bool json_number(cJSON *root, const char *key, float *out)
{
    cJSON *n = cJSON_GetObjectItemCaseSensitive(root, key);
    if (cJSON_IsNumber(n)) {
        *out = (float)n->valuedouble;
        return true;
    }
    return false;
}

static void json_string(cJSON *root, const char *key, char *out, size_t cap)
{
    cJSON *s = cJSON_GetObjectItemCaseSensitive(root, key);
    if (cJSON_IsString(s) && s->valuestring) {
        snprintf(out, cap, "%s", s->valuestring);
    } else {
        out[0] = '\0';
    }
}

static esp_err_t fetch_status(void)
{
    resp_buf_t resp = { 0 };
    int status = 0;
    esp_err_t err = http_get("/status", &resp, &status);
    if (err != ESP_OK || status != 200) {
        ESP_LOGW(TAG, "GET /status failed (err=%s, http=%d)",
                 esp_err_to_name(err), status);
        buf_free(&resp);
        ui_set_offline("server unreachable");
        return ESP_FAIL;
    }

    cJSON *json = cJSON_ParseWithLength(resp.buf, resp.len);
    buf_free(&resp);
    if (!json) {
        ui_set_offline("bad JSON from server");
        return ESP_FAIL;
    }

    ui_status_t st = { 0 };
    cJSON *conn = cJSON_GetObjectItemCaseSensitive(json, "connected");
    st.connected = cJSON_IsTrue(conn);
    st.position_valid = json_number(json, "position_mm", &st.position_mm);
    st.target_valid = json_number(json, "target_mm", &st.target_mm);
    json_string(json, "state", st.state, sizeof(st.state));
    float age = 0;
    if (json_number(json, "age_seconds", &age)) {
        st.age_s = (int)age;
    }
    cJSON_Delete(json);

    ui_set_status(&st);
    return ESP_OK;
}

/* ---------------------- Control commands ---------------------- */

static void execute_command(const rail_command_t *cmd)
{
    int status = 0;

    switch (cmd->type) {
    case RAIL_CMD_JOG_START: {
        const char *path = (cmd->arg >= 0)
            ? "/control/jog/start/positive"
            : "/control/jog/start/negative";
        http_post(path, NULL, &status);
        ESP_LOGI(TAG, "jog start %s -> http %d",
                 (cmd->arg >= 0) ? "+" : "-", status);
        break;
    }
    case RAIL_CMD_JOG_STOP:
        http_post("/control/jog/stop", NULL, &status);
        ESP_LOGI(TAG, "jog stop -> http %d", status);
        break;
    case RAIL_CMD_HOME:
        http_post("/control/home", NULL, &status);
        ESP_LOGI(TAG, "home -> http %d", status);
        break;
    }
}

/* ---------------------- Task ---------------------- */

static void client_task(void *arg)
{
    (void)arg;

    ui_set_offline("WiFi connecting...");
    while (!network_is_connected()) {
        network_wait_connected(2000);
    }

    const uint32_t period_ms = CONFIG_RAIL_POLL_INTERVAL_S * 1000;

    while (1) {
        if (!network_is_connected()) {
            ui_set_offline("WiFi lost, reconnecting...");
            network_wait_connected(5000);
            continue;
        }

        rail_command_t cmd;
        if (xQueueReceive(s_cmd_queue, &cmd, pdMS_TO_TICKS(period_ms))
                == pdTRUE) {
            execute_command(&cmd);
            fetch_status();  /* reflect the change without waiting a cycle */
        } else {
            fetch_status();  /* periodic poll */
        }
    }
}

/* ---------------------- Public API ---------------------- */

esp_err_t rail_client_init(void)
{
    s_cmd_queue = xQueueCreate(CMD_QUEUE_LEN, sizeof(rail_command_t));
    if (!s_cmd_queue) {
        return ESP_ERR_NO_MEM;
    }
    BaseType_t ok = xTaskCreatePinnedToCore(
        client_task, "rail", 6144, NULL, 4, NULL, 0);
    return ok == pdPASS ? ESP_OK : ESP_FAIL;
}

bool rail_client_enqueue(const rail_command_t *cmd)
{
    if (!s_cmd_queue || !cmd) {
        return false;
    }
    return xQueueSend(s_cmd_queue, cmd, 0) == pdTRUE;
}
