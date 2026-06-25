#include "network.h"

#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "nvs.h"

#include "sdkconfig.h"

static const char *TAG = "network";

#define NET_BIT_CONNECTED  BIT0

/* NVS namespace and keys for on-device-provisioned credentials. */
#define CRED_NAMESPACE  "rail_wifi"
#define CRED_KEY_SSID   "ssid"
#define CRED_KEY_PASS   "pass"

static EventGroupHandle_t s_event_group;
static volatile network_state_t s_state = NETWORK_STATE_IDLE;
static esp_netif_t *s_netif;

/* When false, WiFi is started but idle: the event handler does not
 * auto-connect, leaving the stack free to scan and be provisioned. */
static bool s_have_creds;

static void on_wifi_event(void *arg, esp_event_base_t base,
                          int32_t id, void *data)
{
    (void)arg;

    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        if (s_have_creds) {
            ESP_LOGI(TAG, "wifi started, connecting");
            s_state = NETWORK_STATE_CONNECTING;
            esp_wifi_connect();
        } else {
            ESP_LOGI(TAG, "wifi started idle (awaiting provisioning)");
            s_state = NETWORK_STATE_IDLE;
        }
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        wifi_event_sta_disconnected_t *e =
            (wifi_event_sta_disconnected_t *)data;
        ESP_LOGW(TAG, "disconnected, reason=%d", e ? e->reason : -1);
        xEventGroupClearBits(s_event_group, NET_BIT_CONNECTED);
        if (s_have_creds) {
            s_state = NETWORK_STATE_DISCONNECTED;
            esp_wifi_connect();  /* keep retrying with stored creds */
        } else {
            s_state = NETWORK_STATE_IDLE;
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = (ip_event_got_ip_t *)data;
        ESP_LOGI(TAG, "got IP " IPSTR, IP2STR(&e->ip_info.ip));
        s_state = NETWORK_STATE_CONNECTED;
        xEventGroupSetBits(s_event_group, NET_BIT_CONNECTED);
    }
}

static esp_err_t ensure_nvs(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES ||
        err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "nvs reinit (%s)", esp_err_to_name(err));
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    return err;
}

/* Read stored credentials into the caller's buffers. Returns true only
 * when a non-empty SSID is present. */
static bool load_creds(char *ssid, size_t ssid_len,
                       char *pass, size_t pass_len)
{
    nvs_handle_t h;
    if (nvs_open(CRED_NAMESPACE, NVS_READONLY, &h) != ESP_OK) {
        return false;
    }
    bool ok = false;
    size_t sl = ssid_len, pl = pass_len;
    if (nvs_get_str(h, CRED_KEY_SSID, ssid, &sl) == ESP_OK &&
        strlen(ssid) > 0) {
        if (nvs_get_str(h, CRED_KEY_PASS, pass, &pl) != ESP_OK) {
            pass[0] = '\0';  /* open network: empty password is valid */
        }
        ok = true;
    }
    nvs_close(h);
    return ok;
}

static esp_err_t save_creds(const char *ssid, const char *pass)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(CRED_NAMESPACE, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    err = nvs_set_str(h, CRED_KEY_SSID, ssid);
    if (err == ESP_OK) {
        err = nvs_set_str(h, CRED_KEY_PASS, pass ? pass : "");
    }
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    return err;
}

static void apply_sta_config(const char *ssid, const char *pass)
{
    wifi_config_t wcfg = { 0 };
    strncpy((char *)wcfg.sta.ssid, ssid, sizeof(wcfg.sta.ssid) - 1);
    strncpy((char *)wcfg.sta.password, pass ? pass : "",
            sizeof(wcfg.sta.password) - 1);
    wcfg.sta.threshold.authmode =
        (pass && pass[0]) ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    wcfg.sta.pmf_cfg.capable = true;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wcfg));
}

esp_err_t network_init(void)
{
    if (s_event_group == NULL) {
        s_event_group = xEventGroupCreate();
    }

    ESP_ERROR_CHECK(ensure_nvs());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    s_netif = esp_netif_create_default_wifi_sta();

    wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, on_wifi_event, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, on_wifi_event, NULL, NULL));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    /* Our NVS keys are the single source of truth for credentials, so do
     * not let esp_wifi keep its own persisted copy. */
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));

    char ssid[33] = { 0 };
    char pass[65] = { 0 };
    if (load_creds(ssid, sizeof(ssid), pass, sizeof(pass))) {
        ESP_LOGI(TAG, "using stored credentials, ssid=\"%s\"", ssid);
        apply_sta_config(ssid, pass);
        s_have_creds = true;
    } else if (strlen(CONFIG_RAIL_WIFI_SSID) > 0) {
        ESP_LOGI(TAG, "using Kconfig credentials, ssid=\"%s\"",
                 CONFIG_RAIL_WIFI_SSID);
        apply_sta_config(CONFIG_RAIL_WIFI_SSID, CONFIG_RAIL_WIFI_PASSWORD);
        s_have_creds = true;
    } else {
        ESP_LOGW(TAG, "no credentials; starting idle for provisioning");
        s_have_creds = false;
    }

    ESP_ERROR_CHECK(esp_wifi_start());
    return ESP_OK;
}

network_state_t network_get_state(void)
{
    return s_state;
}

bool network_is_connected(void)
{
    return s_state == NETWORK_STATE_CONNECTED;
}

void network_wait_connected(uint32_t timeout_ms)
{
    if (s_event_group == NULL) {
        return;
    }
    TickType_t ticks = (timeout_ms == UINT32_MAX)
        ? portMAX_DELAY
        : pdMS_TO_TICKS(timeout_ms);
    xEventGroupWaitBits(s_event_group, NET_BIT_CONNECTED,
                        pdFALSE, pdTRUE, ticks);
}

bool network_has_credentials(void)
{
    return s_have_creds;
}

int network_scan(network_ap_t *out, int max_aps)
{
    if (!out || max_aps <= 0) {
        return -1;
    }

    wifi_scan_config_t scan_cfg = { 0 };  /* active scan, all channels */
    esp_err_t err = esp_wifi_scan_start(&scan_cfg, true);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "scan start failed: %s", esp_err_to_name(err));
        return -1;
    }

    uint16_t found = 0;
    esp_wifi_scan_get_ap_num(&found);
    if (found == 0) {
        return 0;
    }

    wifi_ap_record_t *recs = calloc(found, sizeof(wifi_ap_record_t));
    if (!recs) {
        /* Still drain the internal list so it does not leak. */
        esp_wifi_clear_ap_list();
        return -1;
    }
    esp_wifi_scan_get_ap_records(&found, recs);

    int n = 0;
    for (int i = 0; i < found && n < max_aps; i++) {
        const char *ssid = (const char *)recs[i].ssid;
        if (ssid[0] == '\0') {
            continue;  /* hidden network */
        }
        bool dup = false;
        for (int j = 0; j < n; j++) {
            if (strcmp(out[j].ssid, ssid) == 0) {
                dup = true;
                break;
            }
        }
        if (dup) {
            continue;
        }
        strncpy(out[n].ssid, ssid, sizeof(out[n].ssid) - 1);
        out[n].ssid[sizeof(out[n].ssid) - 1] = '\0';
        out[n].rssi = recs[i].rssi;
        out[n].secured = (recs[i].authmode != WIFI_AUTH_OPEN);
        n++;
    }
    free(recs);
    ESP_LOGI(TAG, "scan: %d unique networks", n);
    return n;
}

esp_err_t network_set_credentials(const char *ssid, const char *password)
{
    if (!ssid || ssid[0] == '\0') {
        return ESP_ERR_INVALID_ARG;
    }
    esp_err_t err = save_creds(ssid, password);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "save creds failed: %s", esp_err_to_name(err));
        return err;
    }
    apply_sta_config(ssid, password);
    s_have_creds = true;
    s_state = NETWORK_STATE_CONNECTING;
    ESP_LOGI(TAG, "credentials set, connecting to \"%s\"", ssid);
    return esp_wifi_connect();
}

void network_clear_credentials(void)
{
    nvs_handle_t h;
    if (nvs_open(CRED_NAMESPACE, NVS_READWRITE, &h) == ESP_OK) {
        nvs_erase_key(h, CRED_KEY_SSID);
        nvs_erase_key(h, CRED_KEY_PASS);
        nvs_commit(h);
        nvs_close(h);
    }
    s_have_creds = false;
    ESP_LOGW(TAG, "credentials cleared");
}

void network_get_ssid(char *out, size_t len)
{
    if (!out || len == 0) {
        return;
    }
    wifi_ap_record_t ap;
    if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
        snprintf(out, len, "%s", (const char *)ap.ssid);
    } else {
        out[0] = '\0';
    }
}

void network_get_ip(char *out, size_t len)
{
    if (!out || len == 0) {
        return;
    }
    esp_netif_ip_info_t ip;
    if (s_netif && esp_netif_get_ip_info(s_netif, &ip) == ESP_OK &&
        ip.ip.addr != 0) {
        snprintf(out, len, IPSTR, IP2STR(&ip.ip));
    } else {
        out[0] = '\0';
    }
}

int network_get_rssi(void)
{
    wifi_ap_record_t ap;
    if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
        return ap.rssi;
    }
    return 0;
}

void network_get_mac(char *out, size_t len)
{
    if (!out || len == 0) {
        return;
    }
    uint8_t mac[6] = { 0 };
    if (esp_wifi_get_mac(WIFI_IF_STA, mac) == ESP_OK) {
        snprintf(out, len, "%02X:%02X:%02X:%02X:%02X:%02X",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    } else {
        out[0] = '\0';
    }
}
