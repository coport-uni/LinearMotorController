#pragma once

#ifdef __cplusplus
extern "C" {
#endif

/** Called, in the LVGL context, once the device is connected. */
typedef void (*prov_done_cb_t)(void);

/**
 * Build the on-device WiFi provisioning UI on the active screen: a list of
 * scanned networks and an on-screen keyboard for the password. Must be
 * called inside bsp_display_lock / bsp_display_unlock. When the user picks
 * a network, types the password, and the device connects, @p on_done is
 * invoked so the caller can switch to the main UI.
 */
void prov_ui_create(prov_done_cb_t on_done);

#ifdef __cplusplus
}
#endif
