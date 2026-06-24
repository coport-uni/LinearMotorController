#include "ui.h"

#include <stdint.h>

#include "esp_log.h"
#include "bsp/esp-box-3.h"
#include "lvgl.h"

#include "sdkconfig.h"

#include "rail_client.h"

static const char *TAG = "ui";

#define UI_LOCK_MS      50

#define COLOR_BG        lv_color_hex(0x0A0E27)
#define COLOR_MUTED     lv_color_hex(0x9CA3AF)
#define COLOR_OK        lv_color_hex(0x06D6A0)
#define COLOR_PINK      lv_color_hex(0xEF476F)
#define COLOR_ACCENT    lv_color_hex(0x00E5FF)

/* Identifies which control button fired a shared handler. */
typedef enum {
    BTN_JOG_DOWN,   /* negative direction */
    BTN_JOG_UP,     /* positive direction */
    BTN_HOME,
} btn_id_t;

static lv_obj_t *s_dot;
static lv_obj_t *s_lbl_state;
static lv_obj_t *s_lbl_age;
static lv_obj_t *s_val_pos;
static lv_obj_t *s_val_target;
static lv_obj_t *s_val_runstate;
static lv_obj_t *s_lbl_status;

#define UI_WITH_LOCK(BLOCK)                          \
    do {                                             \
        if (bsp_display_lock(UI_LOCK_MS)) {          \
            BLOCK;                                   \
            bsp_display_unlock();                    \
        }                                            \
    } while (0)

/* ---------------------- control buttons ---------------------- */

/* Jog buttons are continuous: start on press, stop on release / press
 * loss, so holding the button moves the rail until let go. */
static void on_jog(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    btn_id_t id = (btn_id_t)(intptr_t)lv_event_get_user_data(e);
    rail_command_t cmd = { 0 };

    if (code == LV_EVENT_PRESSED) {
        cmd.type = RAIL_CMD_JOG_START;
        cmd.arg = (id == BTN_JOG_UP) ? 1.0f : -1.0f;
        rail_client_enqueue(&cmd);
    } else if (code == LV_EVENT_RELEASED || code == LV_EVENT_PRESS_LOST) {
        cmd.type = RAIL_CMD_JOG_STOP;
        rail_client_enqueue(&cmd);
    }
}

static void on_home(lv_event_t *e)
{
    (void)e;
    rail_command_t cmd = { .type = RAIL_CMD_HOME };
    rail_client_enqueue(&cmd);
}

/* ---------------------- builders ---------------------- */

static lv_obj_t *make_reading(const char *name, int y)
{
    lv_obj_t *scr = lv_scr_act();

    lv_obj_t *lbl = lv_label_create(scr);
    lv_label_set_text(lbl, name);
    lv_obj_set_style_text_color(lbl, COLOR_MUTED, 0);
    lv_obj_align(lbl, LV_ALIGN_TOP_LEFT, 4, y);

    lv_obj_t *val = lv_label_create(scr);
    lv_label_set_text(val, "--");
    lv_obj_set_style_text_color(val, lv_color_white(), 0);
    lv_obj_align(val, LV_ALIGN_TOP_LEFT, 90, y);
    return val;
}

static lv_obj_t *make_jog_button(const char *text, int x, int y, btn_id_t id)
{
    lv_obj_t *scr = lv_scr_act();

    lv_obj_t *btn = lv_button_create(scr);
    lv_obj_set_size(btn, 100, 60);
    lv_obj_align(btn, LV_ALIGN_TOP_LEFT, x, y);
    void *ud = (void *)(intptr_t)id;
    lv_obj_add_event_cb(btn, on_jog, LV_EVENT_PRESSED, ud);
    lv_obj_add_event_cb(btn, on_jog, LV_EVENT_RELEASED, ud);
    lv_obj_add_event_cb(btn, on_jog, LV_EVENT_PRESS_LOST, ud);

    lv_obj_t *lbl = lv_label_create(btn);
    lv_label_set_text(lbl, text);
    lv_obj_set_style_text_align(lbl, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_center(lbl);
    return lbl;
}

static lv_obj_t *make_home_button(const char *text, int x, int y)
{
    lv_obj_t *scr = lv_scr_act();

    lv_obj_t *btn = lv_button_create(scr);
    lv_obj_set_size(btn, 100, 60);
    lv_obj_align(btn, LV_ALIGN_TOP_LEFT, x, y);
    lv_obj_add_event_cb(btn, on_home, LV_EVENT_CLICKED, NULL);

    lv_obj_t *lbl = lv_label_create(btn);
    lv_label_set_text(lbl, text);
    lv_obj_set_style_text_align(lbl, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_center(lbl);
    return lbl;
}

/* ---------------------- public API ---------------------- */

void ui_create(void)
{
    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, COLOR_BG, 0);

    /* Top: connection dot + word + reading age. */
    s_dot = lv_obj_create(scr);
    lv_obj_set_size(s_dot, 12, 12);
    lv_obj_set_style_radius(s_dot, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_border_width(s_dot, 0, 0);
    lv_obj_set_style_pad_all(s_dot, 0, 0);
    lv_obj_set_style_bg_color(s_dot, COLOR_MUTED, 0);
    lv_obj_align(s_dot, LV_ALIGN_TOP_LEFT, 4, 5);
    lv_obj_clear_flag(s_dot, LV_OBJ_FLAG_SCROLLABLE);

    s_lbl_state = lv_label_create(scr);
    lv_label_set_text(s_lbl_state, "starting");
    lv_obj_set_style_text_color(s_lbl_state, COLOR_MUTED, 0);
    lv_obj_align(s_lbl_state, LV_ALIGN_TOP_LEFT, 24, 2);

    s_lbl_age = lv_label_create(scr);
    lv_label_set_text(s_lbl_age, "");
    lv_obj_set_style_text_color(s_lbl_age, COLOR_MUTED, 0);
    lv_obj_align(s_lbl_age, LV_ALIGN_TOP_RIGHT, -4, 2);

    /* Readings. */
    s_val_pos      = make_reading("Position", 34);
    s_val_target   = make_reading("Target",   62);
    s_val_runstate = make_reading("State",    90);

    /* Control buttons: one row of three. */
    make_jog_button("Jog\n-", 6, 124, BTN_JOG_DOWN);
    make_jog_button("Jog\n+", 110, 124, BTN_JOG_UP);
    make_home_button("Home", 214, 124);

    /* Footer status line. */
    s_lbl_status = lv_label_create(scr);
    lv_label_set_text(s_lbl_status, "starting...");
    lv_obj_set_style_text_color(s_lbl_status, COLOR_MUTED, 0);
    lv_obj_set_width(s_lbl_status, 320);
    lv_label_set_long_mode(s_lbl_status, LV_LABEL_LONG_DOT);
    lv_obj_align(s_lbl_status, LV_ALIGN_BOTTOM_LEFT, 4, -2);

    ESP_LOGI(TAG, "ui ready");
}

void ui_set_status(const ui_status_t *st)
{
    if (!st) {
        return;
    }
    UI_WITH_LOCK({
        lv_color_t c = st->connected ? COLOR_OK : COLOR_PINK;
        lv_obj_set_style_bg_color(s_dot, c, 0);
        lv_label_set_text(s_lbl_state,
                          st->connected ? "online" : "rail offline");
        lv_obj_set_style_text_color(s_lbl_state, c, 0);
        lv_label_set_text_fmt(s_lbl_age, "%ds", st->age_s);

        if (st->connected) {
            if (st->position_valid) {
                lv_label_set_text_fmt(s_val_pos, "%.2f mm", st->position_mm);
            } else {
                lv_label_set_text(s_val_pos, "-- mm");
            }
            if (st->target_valid) {
                lv_label_set_text_fmt(s_val_target, "%.2f mm",
                                      st->target_mm);
            } else {
                lv_label_set_text(s_val_target, "--");
            }
            lv_label_set_text(s_val_runstate,
                              st->state[0] ? st->state : "--");
            lv_label_set_text_fmt(s_lbl_status, "updated %ds ago",
                                  st->age_s);
        } else {
            lv_label_set_text(s_val_pos, "-- mm");
            lv_label_set_text(s_val_target, "--");
            lv_label_set_text(s_val_runstate, "--");
            lv_label_set_text(s_lbl_status, "rail offline");
        }
        lv_obj_set_style_text_color(s_lbl_status, COLOR_MUTED, 0);
    });
}

void ui_set_offline(const char *reason)
{
    UI_WITH_LOCK({
        lv_obj_set_style_bg_color(s_dot, COLOR_MUTED, 0);
        lv_label_set_text(s_lbl_state, "offline");
        lv_obj_set_style_text_color(s_lbl_state, COLOR_MUTED, 0);
        lv_label_set_text(s_lbl_age, "");
        lv_label_set_text(s_val_pos, "-- mm");
        lv_label_set_text(s_val_target, "--");
        lv_label_set_text(s_val_runstate, "--");
        lv_label_set_text(s_lbl_status, reason ? reason : "offline");
        lv_obj_set_style_text_color(s_lbl_status, COLOR_ACCENT, 0);
    });
}
