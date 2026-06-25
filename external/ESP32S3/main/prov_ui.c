#include "prov_ui.h"

#include <stdint.h>
#include <string.h>

#include "esp_log.h"
#include "lvgl.h"

#include "network.h"

static const char *TAG = "prov_ui";

#define MAX_APS         20
#define CONN_POLL_MS    500
#define CONN_TRIES_MAX  30   /* 30 x 500 ms = 15 s before giving up */

#define COLOR_BG        lv_color_hex(0x0A0E27)
#define COLOR_MUTED     lv_color_hex(0x9CA3AF)
#define COLOR_OK        lv_color_hex(0x06D6A0)
#define COLOR_PINK      lv_color_hex(0xEF476F)
#define COLOR_ACCENT    lv_color_hex(0x00E5FF)

static prov_done_cb_t s_done;

static lv_obj_t *s_list_view;
static lv_obj_t *s_pass_view;
static lv_obj_t *s_ap_list;
static lv_obj_t *s_scan_status;
static lv_obj_t *s_ssid_lbl;
static lv_obj_t *s_ta;
static lv_obj_t *s_pass_status;

static network_ap_t s_aps[MAX_APS];
static int          s_ap_count;
static char         s_sel_ssid[33];
static lv_timer_t  *s_conn_timer;
static int          s_conn_tries;

/* ---------------------- scanning ---------------------- */

static void on_ap_clicked(lv_event_t *e);

static void do_scan_now(lv_timer_t *t)
{
    s_ap_count = network_scan(s_aps, MAX_APS);
    if (s_ap_count < 0) {
        s_ap_count = 0;
        lv_label_set_text(s_scan_status, "scan failed");
    } else if (s_ap_count == 0) {
        lv_label_set_text(s_scan_status, "no networks found");
    } else {
        lv_label_set_text_fmt(s_scan_status, "%d networks", s_ap_count);
    }

    lv_obj_clean(s_ap_list);
    for (int i = 0; i < s_ap_count; i++) {
        const char *icon = s_aps[i].secured ? LV_SYMBOL_WIFI : LV_SYMBOL_USB;
        lv_obj_t *btn = lv_list_add_button(s_ap_list, icon, s_aps[i].ssid);
        lv_obj_set_user_data(btn, (void *)(intptr_t)i);
        lv_obj_add_event_cb(btn, on_ap_clicked, LV_EVENT_CLICKED, NULL);
    }
    lv_timer_delete(t);  /* one-shot */
}

static void start_scan(void)
{
    lv_label_set_text(s_scan_status, "scanning...");
    /* Run the (blocking) scan from a timer so "scanning..." renders first. */
    lv_timer_create(do_scan_now, 60, NULL);
}

static void on_rescan(lv_event_t *e)
{
    (void)e;
    start_scan();
}

/* ---------------------- password entry ---------------------- */

static void show_list_view(void)
{
    lv_obj_add_flag(s_pass_view, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(s_list_view, LV_OBJ_FLAG_HIDDEN);
}

static void on_ap_clicked(lv_event_t *e)
{
    lv_obj_t *btn = lv_event_get_target(e);
    const char *txt = lv_list_get_button_text(s_ap_list, btn);
    if (!txt) {
        return;
    }
    strncpy(s_sel_ssid, txt, sizeof(s_sel_ssid) - 1);
    s_sel_ssid[sizeof(s_sel_ssid) - 1] = '\0';

    lv_label_set_text_fmt(s_ssid_lbl, "Wi-Fi: %s", s_sel_ssid);
    lv_textarea_set_text(s_ta, "");
    lv_label_set_text(s_pass_status, "enter password, then press OK");
    lv_obj_set_style_text_color(s_pass_status, COLOR_MUTED, 0);

    lv_obj_add_flag(s_list_view, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(s_pass_view, LV_OBJ_FLAG_HIDDEN);
}

static void conn_poll(lv_timer_t *t)
{
    if (network_is_connected()) {
        lv_timer_delete(t);
        s_conn_timer = NULL;
        ESP_LOGI(TAG, "connected; handing off to main UI");
        if (s_done) {
            s_done();
        }
        return;
    }
    if (++s_conn_tries >= CONN_TRIES_MAX) {
        lv_timer_delete(t);
        s_conn_timer = NULL;
        lv_label_set_text(s_pass_status, "failed - check password, press OK");
        lv_obj_set_style_text_color(s_pass_status, COLOR_PINK, 0);
    }
}

static void on_kb_event(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);

    if (code == LV_EVENT_CANCEL) {
        show_list_view();
        return;
    }
    if (code != LV_EVENT_READY) {
        return;
    }

    const char *pass = lv_textarea_get_text(s_ta);
    ESP_LOGI(TAG, "applying credentials for \"%s\"", s_sel_ssid);
    esp_err_t err = network_set_credentials(s_sel_ssid, pass);
    if (err != ESP_OK) {
        lv_label_set_text(s_pass_status, "could not save credentials");
        lv_obj_set_style_text_color(s_pass_status, COLOR_PINK, 0);
        return;
    }
    lv_label_set_text(s_pass_status, "connecting...");
    lv_obj_set_style_text_color(s_pass_status, COLOR_ACCENT, 0);

    s_conn_tries = 0;
    if (s_conn_timer) {
        lv_timer_delete(s_conn_timer);
    }
    s_conn_timer = lv_timer_create(conn_poll, CONN_POLL_MS, NULL);
}

/* ---------------------- build ---------------------- */

static lv_obj_t *make_full_container(lv_obj_t *parent)
{
    lv_obj_t *c = lv_obj_create(parent);
    lv_obj_set_size(c, 320, 240);
    lv_obj_align(c, LV_ALIGN_TOP_LEFT, 0, 0);
    lv_obj_set_style_bg_color(c, COLOR_BG, 0);
    lv_obj_set_style_border_width(c, 0, 0);
    lv_obj_set_style_pad_all(c, 4, 0);
    lv_obj_set_style_radius(c, 0, 0);
    lv_obj_clear_flag(c, LV_OBJ_FLAG_SCROLLABLE);
    return c;
}

void prov_ui_create(prov_done_cb_t on_done)
{
    s_done = on_done;

    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, COLOR_BG, 0);

    /* ---- list view ---- */
    s_list_view = make_full_container(scr);

    lv_obj_t *title = lv_label_create(s_list_view);
    lv_label_set_text(title, "Select Wi-Fi");
    lv_obj_set_style_text_color(title, lv_color_white(), 0);
    lv_obj_align(title, LV_ALIGN_TOP_LEFT, 2, 2);

    lv_obj_t *scan_btn = lv_button_create(s_list_view);
    lv_obj_set_size(scan_btn, 80, 30);
    lv_obj_align(scan_btn, LV_ALIGN_TOP_RIGHT, -2, -2);
    lv_obj_add_event_cb(scan_btn, on_rescan, LV_EVENT_CLICKED, NULL);
    lv_obj_t *scan_lbl = lv_label_create(scan_btn);
    lv_label_set_text(scan_lbl, LV_SYMBOL_REFRESH " Scan");
    lv_obj_center(scan_lbl);

    s_scan_status = lv_label_create(s_list_view);
    lv_label_set_text(s_scan_status, "scanning...");
    lv_obj_set_style_text_color(s_scan_status, COLOR_MUTED, 0);
    lv_obj_align(s_scan_status, LV_ALIGN_BOTTOM_LEFT, 2, -2);

    s_ap_list = lv_list_create(s_list_view);
    lv_obj_set_size(s_ap_list, 308, 178);
    lv_obj_align(s_ap_list, LV_ALIGN_TOP_LEFT, 0, 36);

    /* ---- password view (hidden until a network is picked) ---- */
    s_pass_view = make_full_container(scr);
    lv_obj_add_flag(s_pass_view, LV_OBJ_FLAG_HIDDEN);

    s_ssid_lbl = lv_label_create(s_pass_view);
    lv_label_set_text(s_ssid_lbl, "Wi-Fi:");
    lv_obj_set_style_text_color(s_ssid_lbl, lv_color_white(), 0);
    lv_obj_align(s_ssid_lbl, LV_ALIGN_TOP_LEFT, 2, 2);

    s_ta = lv_textarea_create(s_pass_view);
    lv_textarea_set_one_line(s_ta, true);
    lv_textarea_set_password_mode(s_ta, true);
    lv_textarea_set_placeholder_text(s_ta, "password");
    lv_obj_set_width(s_ta, 300);
    lv_obj_align(s_ta, LV_ALIGN_TOP_LEFT, 2, 26);

    s_pass_status = lv_label_create(s_pass_view);
    lv_label_set_text(s_pass_status, "enter password, then press OK");
    lv_obj_set_style_text_color(s_pass_status, COLOR_MUTED, 0);
    lv_obj_align(s_pass_status, LV_ALIGN_TOP_LEFT, 2, 66);

    lv_obj_t *kb = lv_keyboard_create(s_pass_view);
    lv_keyboard_set_textarea(kb, s_ta);
    lv_obj_add_event_cb(kb, on_kb_event, LV_EVENT_READY, NULL);
    lv_obj_add_event_cb(kb, on_kb_event, LV_EVENT_CANCEL, NULL);

    ESP_LOGI(TAG, "provisioning ui ready");
    start_scan();
}
