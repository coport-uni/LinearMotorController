#include <stdio.h>

#include "esp_log.h"
#include "esp_system.h"

#include "bsp/esp-box-3.h"

#include "sdkconfig.h"

#include "ui.h"
#include "prov_ui.h"
#include "buttons_check.h"
#include "network.h"
#include "rail_client.h"

static const char *TAG = "main";

/* Build the rail control UI on the active screen and start polling. Assumes
 * the display lock is already held (it is at boot and in the LVGL context
 * from which on_provisioned() is called). */
static void start_running(void)
{
    lv_obj_clean(lv_scr_act());
    ui_create();
    rail_client_init();
}

/* Invoked by the provisioning UI, in the LVGL context, once connected. */
static void on_provisioned(void)
{
    ESP_LOGI(TAG, "provisioned; switching to control UI");
    start_running();
}

/* The on-board CONFIG button homes the rail; a long press forgets the WiFi
 * credentials and reboots into provisioning (use when the network changes). */
static void on_config_pressed(void)
{
    rail_command_t cmd = { .type = RAIL_CMD_HOME };
    rail_client_enqueue(&cmd);
}

static void on_config_long_pressed(void)
{
    ESP_LOGW(TAG, "long press: clearing WiFi credentials and rebooting");
    network_clear_credentials();
    esp_restart();
}

void app_main(void)
{
    ESP_LOGI(TAG, "Rail monitor starting");

    ESP_ERROR_CHECK(bsp_i2c_init());
    bsp_display_start();
    bsp_display_backlight_on();

    network_init();

    buttons_callbacks_t btn_cbs = {
        .on_config      = on_config_pressed,
        .on_mute        = NULL,
        .on_config_long = on_config_long_pressed,
    };
    buttons_check_init(&btn_cbs);

    bsp_display_lock(0);
    if (network_has_credentials()) {
        ui_create();
        rail_client_init();
    } else {
        prov_ui_create(on_provisioned);
    }
    bsp_display_unlock();

    ESP_LOGI(TAG, "init complete");
}
