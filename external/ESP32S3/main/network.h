#pragma once

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    NETWORK_STATE_IDLE,
    NETWORK_STATE_CONNECTING,
    NETWORK_STATE_CONNECTED,
    NETWORK_STATE_DISCONNECTED,
} network_state_t;

/** One scanned access point, returned by network_scan(). */
typedef struct {
    char    ssid[33];
    int8_t  rssi;
    bool    secured;   /* true unless the AP is open (no password) */
} network_ap_t;

/**
 * @brief  Bring up the WiFi STA stack non-blockingly.
 *
 * Initializes NVS, esp_netif, the default event loop and esp_wifi in
 * station mode, then starts WiFi. Credentials are loaded from NVS (set by
 * on-device provisioning) if present, otherwise from CONFIG_RAIL_WIFI_SSID
 * / CONFIG_RAIL_WIFI_PASSWORD when those are non-empty. If neither source
 * has credentials, WiFi starts idle (ready for network_scan() and
 * network_set_credentials()) and does not attempt to connect.
 */
esp_err_t       network_init(void);

/**
 * @brief  Return the current WiFi STA connection state.
 */
network_state_t network_get_state(void);

/**
 * @brief  Convenience predicate: link is up and an IP has been acquired.
 */
bool            network_is_connected(void);

/**
 * @brief  Block the caller until the link is up or the timeout expires.
 *
 * @param  timeout_ms  Maximum time to wait. 0 returns immediately.
 *                     UINT32_MAX waits forever.
 */
void            network_wait_connected(uint32_t timeout_ms);

/**
 * @brief  Whether usable credentials were loaded at network_init().
 *
 * When false, the caller should start on-device provisioning instead of
 * the normal monitor flow.
 */
bool            network_has_credentials(void);

/**
 * @brief  Scan for nearby access points (blocking, a few seconds).
 *
 * Fills @p out with up to @p max_aps unique, named networks sorted by the
 * order esp_wifi returns them. WiFi must already be started (it is after
 * network_init()).
 *
 * @return Number of APs written, or -1 on error.
 */
int             network_scan(network_ap_t *out, int max_aps);

/**
 * @brief  Apply credentials, persist them to NVS, and connect.
 *
 * Used by the provisioning UI once the user picks an SSID and types a
 * password. After this, network_has_credentials() returns true on the
 * next boot and the device connects automatically.
 */
esp_err_t       network_set_credentials(const char *ssid,
                                        const char *password);

/**
 * @brief  Erase the stored credentials from NVS.
 *
 * The change takes effect on the next boot, which then starts in the
 * provisioning flow. Typically followed by esp_restart().
 */
void            network_clear_credentials(void);

/** Fill @p out with the connected SSID, or "" if not connected. */
void            network_get_ssid(char *out, size_t len);

/** Fill @p out with the STA IPv4 address, or "" if none. */
void            network_get_ip(char *out, size_t len);

/** Current STA signal strength in dBm, or 0 if not connected. */
int             network_get_rssi(void);

/** Fill @p out with the STA MAC address formatted "AA:BB:CC:DD:EE:FF". */
void            network_get_mac(char *out, size_t len);

#ifdef __cplusplus
}
#endif
