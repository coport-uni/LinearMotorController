#include <stdio.h>

#include "esp_log.h"

#include "bsp/esp-box-3.h"

#include "sdkconfig.h"

#include "ui.h"
#include "buttons_check.h"
#include "network.h"
#include "rail_client.h"

static const char *TAG = "main";

/* The on-board CONFIG button homes the rail, so the demo can return to
 * the origin without the touchscreen. */
static void on_config_pressed(void)
{
    rail_command_t cmd = { .type = RAIL_CMD_HOME };
    rail_client_enqueue(&cmd);
}

void app_main(void)
{
    ESP_LOGI(TAG, "Rail monitor starting");

    ESP_ERROR_CHECK(bsp_i2c_init());
    bsp_display_start();
    bsp_display_backlight_on();

    bsp_display_lock(0);
    ui_create();
    bsp_display_unlock();

    buttons_callbacks_t btn_cbs = {
        .on_config = on_config_pressed,
        .on_mute   = NULL,
    };
    buttons_check_init(&btn_cbs);

    network_init();
    ESP_ERROR_CHECK(rail_client_init());

    ESP_LOGI(TAG, "init complete");
}
