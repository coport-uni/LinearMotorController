#include "ui.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "lvgl.h"

#include "rail_client.h"
#include "network.h"

/* This UI is a faithful port of the ESP32S3BOX3MotorController touch UI
 * (X/Z quadrant dial + Y buttons + Move plot + Status tabs). The original
 * drove MKS motors over a USB serial bridge; here the rail is the Y axis
 * and its buttons drive the FastAPI server over WiFi (rail_client). The
 * X/Z dial and the Move plot are kept as placeholders for the future
 * pipette-station motors, so they have no backend yet. */

/* ---- Display dimensions ---- */
#define SCR_W  320
#define SCR_H  240

#define TAB_BAR_H  28
#define CONTENT_H  (SCR_H - TAB_BAR_H)

/* ---- Dial (X/Z quadrant circle) ---- */
#define LEFT_W  210
#define DIAL_D  180
#define DIAL_X  ((LEFT_W - DIAL_D) / 2)
#define DIAL_Y  ((CONTENT_H - DIAL_D) / 2)

/* ---- Y (rail) panel ---- */
#define RIGHT_X  (LEFT_W + 4)
#define RIGHT_W  (SCR_W - LEFT_W - 4)
#define Y_BTN_H  ((CONTENT_H / 2) - 6)

/* ---- Colours ---- */
#define COL_BG       0x1A1A2E
#define COL_Z        0x2E86C1
#define COL_Z_PR     0x1A4F72
#define COL_X        0x1E8449
#define COL_X_PR     0x0E6251
#define COL_Y        0xB7770D
#define COL_Y_PR     0x5B3B06
#define COL_HOME     0xC0392B
#define COL_TEXT     0xECF0F1
#define COL_TEXT_DIM 0x808896
#define COL_OK       0x4CAF50
#define COL_WARN     0xFFC107
#define COL_BAD      0xE53935
#define COL_OFF      0x404858
#define HOME_BTN_D 44

/* Dial visual state (X/Z are placeholders: touch highlights but sends
 * no command — only the centre Home and the Y buttons act). */
typedef enum { AXIS_X, AXIS_Z } dial_axis_t;
typedef enum { DIR_POS, DIR_NEG } dial_dir_t;

static dial_axis_t s_active_axis;
static dial_dir_t  s_active_dir;
static bool        s_dial_pressed;

/* Latest rail status, written by rail_client (other task) and read by the
 * 1 Hz Status-tab refresh timer. Plain-data copy; a torn read only blips a
 * status label, so no lock is taken (matches the original UI's approach). */
static ui_status_t s_rail;
static bool        s_rail_link;
static char        s_rail_reason[40] = "starting...";

/* ---- Status-tab widgets ---- */
static lv_obj_t *s_lbl_wifi_state;
static lv_obj_t *s_lbl_ssid;
static lv_obj_t *s_lbl_ip;
static lv_obj_t *s_lbl_rssi;
static lv_obj_t *s_lbl_mac;
static lv_obj_t *s_rssi_bars[4];
static lv_obj_t *s_lbl_srv_state;
static lv_obj_t *s_lbl_rail_pos;
static lv_obj_t *s_lbl_rail_age;

/* ---- Move-tab geometry ---- */
#define PLOT_SIZE       160
#define PLOT_X_OFFSET   25
#define PLOT_Y_OFFSET   4
#define MARKER_R        6
#define GRID_STEP_MM    20
#define GRID_MAJOR_MM   100
#define MAX_TRAVEL_MM   400

static lv_obj_t *s_plot;
static lv_obj_t *s_v_line;
static lv_obj_t *s_h_line;
static lv_obj_t *s_marker;
static lv_obj_t *s_lbl_target_x;
static lv_obj_t *s_lbl_target_z;
static int s_target_x_mm = 0;
static int s_target_z_mm = 0;

/* ---------------------- dial drawing ---------------------- */

static void draw_sector(lv_layer_t *layer, int32_t cx, int32_t cy, int32_t r,
                        int32_t start_angle, int32_t end_angle, uint32_t colour)
{
    lv_draw_arc_dsc_t dsc;
    lv_draw_arc_dsc_init(&dsc);
    dsc.center.x   = cx;
    dsc.center.y   = cy;
    dsc.radius     = (uint16_t)r;
    dsc.width      = (uint16_t)r;
    dsc.start_angle = start_angle;
    dsc.end_angle   = end_angle;
    dsc.color      = lv_color_hex(colour);
    dsc.opa        = LV_OPA_COVER;
    lv_draw_arc(layer, &dsc);
}

static void dial_draw_cb(lv_event_t *e)
{
    lv_layer_t *layer = lv_event_get_layer(e);
    lv_obj_t   *obj   = lv_event_get_target(e);

    lv_area_t a;
    lv_obj_get_coords(obj, &a);
    int32_t cx = (a.x1 + a.x2) / 2;
    int32_t cy = (a.y1 + a.y2) / 2;
    int32_t r  = (a.x2 - a.x1) / 2;

    bool pr = s_dial_pressed;
    uint32_t z_top = (pr && s_active_axis == AXIS_Z && s_active_dir == DIR_POS)
                     ? COL_Z_PR : COL_Z;
    uint32_t z_bot = (pr && s_active_axis == AXIS_Z && s_active_dir == DIR_NEG)
                     ? COL_Z_PR : COL_Z;
    uint32_t x_rgt = (pr && s_active_axis == AXIS_X && s_active_dir == DIR_POS)
                     ? COL_X_PR : COL_X;
    uint32_t x_lft = (pr && s_active_axis == AXIS_X && s_active_dir == DIR_NEG)
                     ? COL_X_PR : COL_X;

    draw_sector(layer, cx, cy, r, 225, 315, z_top);
    draw_sector(layer, cx, cy, r, 315, 360, x_rgt);
    draw_sector(layer, cx, cy, r,   0,  45, x_rgt);
    draw_sector(layer, cx, cy, r,  45, 135, z_bot);
    draw_sector(layer, cx, cy, r, 135, 225, x_lft);

    int32_t d = r * 707 / 1000;
    lv_draw_line_dsc_t ln;
    lv_draw_line_dsc_init(&ln);
    ln.color = lv_color_hex(COL_BG);
    ln.width = 3;
    ln.opa   = LV_OPA_COVER;
    ln.p1.x = cx - d; ln.p1.y = cy - d;
    ln.p2.x = cx + d; ln.p2.y = cy + d;
    lv_draw_line(layer, &ln);
    ln.p1.x = cx + d; ln.p1.y = cy - d;
    ln.p2.x = cx - d; ln.p2.y = cy + d;
    lv_draw_line(layer, &ln);
}

static void decode_touch(lv_event_t *e, lv_obj_t *obj,
                         dial_axis_t *axis, dial_dir_t *dir)
{
    lv_indev_t *indev = lv_event_get_indev(e);
    if (!indev) indev = lv_indev_active();
    lv_point_t pt = {0, 0};
    if (indev) lv_indev_get_point(indev, &pt);

    lv_area_t area;
    lv_obj_get_coords(obj, &area);
    int32_t dx = pt.x - (area.x1 + area.x2) / 2;
    int32_t dy = pt.y - (area.y1 + area.y2) / 2;

    if (LV_ABS(dy) >= LV_ABS(dx)) {
        *axis = AXIS_Z;
        *dir  = (dy < 0) ? DIR_POS : DIR_NEG;
    } else {
        *axis = AXIS_X;
        *dir  = (dx > 0) ? DIR_POS : DIR_NEG;
    }
}

/* X/Z dial: visual feedback only — these axes are reserved for the future
 * pipette station, so no motion command is sent. */
static void dial_event_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    lv_obj_t       *obj  = lv_event_get_target(e);

    if (code == LV_EVENT_PRESSED) {
        decode_touch(e, obj, &s_active_axis, &s_active_dir);
        s_dial_pressed = true;
        lv_obj_invalidate(obj);
    } else if (code == LV_EVENT_RELEASED || code == LV_EVENT_PRESS_LOST) {
        s_dial_pressed = false;
        lv_obj_invalidate(obj);
    }
}

static void home_event_cb(lv_event_t *e)
{
    (void)e;
    rail_command_t cmd = { .type = RAIL_CMD_HOME };
    rail_client_enqueue(&cmd);
}

static lv_obj_t *create_dial(lv_obj_t *parent)
{
    lv_obj_t *btn = lv_button_create(parent);
    lv_obj_set_size(btn, DIAL_D, DIAL_D);
    lv_obj_set_pos(btn, DIAL_X, DIAL_Y);
    lv_obj_set_style_border_width(btn, 0, 0);
    lv_obj_set_style_shadow_width(btn, 0, 0);
    lv_obj_set_style_bg_color(btn, lv_color_hex(COL_BG), 0);
    lv_obj_set_style_bg_color(btn, lv_color_hex(COL_BG), LV_STATE_PRESSED);
    lv_obj_clear_flag(btn, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_add_event_cb(btn, dial_draw_cb,  LV_EVENT_DRAW_MAIN,  NULL);
    lv_obj_add_event_cb(btn, dial_event_cb, LV_EVENT_PRESSED,    NULL);
    lv_obj_add_event_cb(btn, dial_event_cb, LV_EVENT_RELEASED,   NULL);
    lv_obj_add_event_cb(btn, dial_event_cb, LV_EVENT_PRESS_LOST, NULL);

    static const struct {
        const char *text;
        lv_align_t  align;
        int32_t     ox, oy;
    } labels[4] = {
        { "Z " LV_SYMBOL_UP,    LV_ALIGN_TOP_MID,    0,  8 },
        { "Z " LV_SYMBOL_DOWN,  LV_ALIGN_BOTTOM_MID, 0, -8 },
        { LV_SYMBOL_LEFT " X",  LV_ALIGN_LEFT_MID,   8,  0 },
        { "X " LV_SYMBOL_RIGHT, LV_ALIGN_RIGHT_MID, -8,  0 },
    };
    for (int i = 0; i < 4; i++) {
        lv_obj_t *lbl = lv_label_create(parent);
        lv_label_set_text(lbl, labels[i].text);
        lv_obj_set_style_text_color(lbl, lv_color_hex(COL_TEXT), 0);
        lv_obj_set_style_text_font(lbl, &lv_font_montserrat_18, 0);
        lv_obj_align_to(lbl, btn, labels[i].align, labels[i].ox, labels[i].oy);
    }

    /* Centre Home button -> rail home over WiFi. */
    lv_obj_t *hbtn = lv_button_create(parent);
    lv_obj_set_size(hbtn, HOME_BTN_D, HOME_BTN_D);
    lv_obj_align_to(hbtn, btn, LV_ALIGN_CENTER, 0, 0);
    lv_obj_set_style_radius(hbtn, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(hbtn, lv_color_hex(COL_HOME), 0);
    lv_obj_set_style_bg_color(hbtn,
        lv_color_hex(COL_HOME >> 1 & 0x7F7F7F), LV_STATE_PRESSED);
    lv_obj_set_style_border_width(hbtn, 0, 0);
    lv_obj_set_style_shadow_width(hbtn, 0, 0);
    lv_obj_add_event_cb(hbtn, home_event_cb, LV_EVENT_CLICKED, NULL);

    lv_obj_t *hlbl = lv_label_create(hbtn);
    lv_label_set_text(hlbl, LV_SYMBOL_HOME);
    lv_obj_set_style_text_color(hlbl, lv_color_hex(COL_TEXT), 0);
    lv_obj_center(hlbl);

    return btn;
}

/* ---------------------- Y (rail) buttons ---------------------- */

/* Hold-to-jog: press starts a continuous jog in the button's direction,
 * release (or press-loss) stops it. The server also stops at a soft limit
 * or after a max duration, so a dropped stop cannot run the rail away. */
static void y_jog_event_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    float dir = (float)(intptr_t)lv_event_get_user_data(e);
    rail_command_t cmd = { 0 };

    if (code == LV_EVENT_PRESSED) {
        cmd.type = RAIL_CMD_JOG_START;
        cmd.arg  = dir;
        rail_client_enqueue(&cmd);
    } else if (code == LV_EVENT_RELEASED || code == LV_EVENT_PRESS_LOST) {
        cmd.type = RAIL_CMD_JOG_STOP;
        rail_client_enqueue(&cmd);
    }
}

static void make_y_btn(lv_obj_t *parent, lv_coord_t x, lv_coord_t y,
                       lv_coord_t w, lv_coord_t h, const char *text,
                       float dir)
{
    lv_obj_t *btn = lv_button_create(parent);
    lv_obj_set_pos(btn, x, y);
    lv_obj_set_size(btn, w, h);
    lv_obj_set_style_bg_color(btn, lv_color_hex(COL_Y), 0);
    lv_obj_set_style_bg_opa(btn, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(btn, 10, 0);
    lv_obj_set_style_border_width(btn, 0, 0);
    lv_obj_set_style_bg_color(btn, lv_color_hex(COL_Y_PR), LV_STATE_PRESSED);

    void *ud = (void *)(intptr_t)dir;
    lv_obj_add_event_cb(btn, y_jog_event_cb, LV_EVENT_PRESSED,    ud);
    lv_obj_add_event_cb(btn, y_jog_event_cb, LV_EVENT_RELEASED,   ud);
    lv_obj_add_event_cb(btn, y_jog_event_cb, LV_EVENT_PRESS_LOST, ud);

    lv_obj_t *lbl = lv_label_create(btn);
    lv_label_set_text(lbl, text);
    lv_obj_set_style_text_color(lbl, lv_color_hex(COL_TEXT), 0);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_18, 0);
    lv_obj_center(lbl);
}

static void build_control_tab(lv_obj_t *tab)
{
    lv_obj_set_style_pad_all(tab, 0, 0);
    lv_obj_set_style_bg_color(tab, lv_color_hex(COL_BG), 0);
    lv_obj_set_style_bg_opa(tab, LV_OPA_COVER, 0);
    lv_obj_clear_flag(tab, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *div = lv_obj_create(tab);
    lv_obj_remove_style_all(div);
    lv_obj_set_pos(div, LEFT_W, 0);
    lv_obj_set_size(div, 4, CONTENT_H);
    lv_obj_set_style_bg_color(div, lv_color_hex(0x3D3D3D), 0);
    lv_obj_set_style_bg_opa(div, LV_OPA_COVER, 0);

    create_dial(tab);

    /* Y axis = the linear rail. Up = positive, Down = negative. */
    make_y_btn(tab, RIGHT_X, 2, RIGHT_W, Y_BTN_H,
               "Y " LV_SYMBOL_UP, 1.0f);
    make_y_btn(tab, RIGHT_X, CONTENT_H / 2 + 2, RIGHT_W, Y_BTN_H,
               "Y " LV_SYMBOL_DOWN, -1.0f);
}

/* ---------------------- Status tab ---------------------- */

static int rssi_to_bars(int rssi)
{
    if (rssi == 0)   return 0;
    if (rssi >= -50) return 4;
    if (rssi >= -65) return 3;
    if (rssi >= -75) return 2;
    if (rssi >= -85) return 1;
    return 0;
}

static const char *rssi_quality_label(int rssi)
{
    switch (rssi_to_bars(rssi)) {
    case 4:  return "excellent";
    case 3:  return "good";
    case 2:  return "fair";
    case 1:  return "weak";
    default: return rssi == 0 ? "-" : "lost";
    }
}

static void build_rssi_bars(lv_obj_t *parent, int x, int baseline_y)
{
    const int bar_w = 5, bar_gap = 3;
    const int heights[4] = { 5, 9, 13, 17 };
    for (int i = 0; i < 4; i++) {
        lv_obj_t *bar = lv_obj_create(parent);
        lv_obj_remove_style_all(bar);
        lv_obj_set_size(bar, bar_w, heights[i]);
        lv_obj_set_pos(bar, x + i * (bar_w + bar_gap), baseline_y - heights[i]);
        lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(bar, 1, 0);
        lv_obj_set_style_bg_color(bar, lv_color_hex(COL_OFF), 0);
        s_rssi_bars[i] = bar;
    }
}

static void update_rssi_bars(int rssi)
{
    int lit = rssi_to_bars(rssi);
    uint32_t lit_col = (lit >= 3) ? COL_OK : (lit >= 2) ? COL_WARN : COL_BAD;
    for (int i = 0; i < 4; i++) {
        lv_obj_set_style_bg_color(s_rssi_bars[i],
            lv_color_hex(i < lit ? lit_col : COL_OFF), 0);
    }
}

static void add_kv_row(lv_obj_t *parent, int x, int y,
                       const char *key, lv_obj_t **value_out)
{
    lv_obj_t *k = lv_label_create(parent);
    lv_label_set_text(k, key);
    lv_obj_set_style_text_color(k, lv_color_hex(COL_TEXT_DIM), 0);
    lv_obj_set_style_text_font(k, &lv_font_montserrat_14, 0);
    lv_obj_set_pos(k, x, y);

    lv_obj_t *v = lv_label_create(parent);
    lv_label_set_text(v, "-");
    lv_obj_set_style_text_color(v, lv_color_hex(COL_TEXT), 0);
    lv_obj_set_style_text_font(v, &lv_font_montserrat_14, 0);
    lv_obj_set_pos(v, x + 64, y);
    *value_out = v;
}

static void status_refresh_cb(lv_timer_t *t)
{
    (void)t;
    char buf[40];

    const char *state_str;
    switch (network_get_state()) {
    case NETWORK_STATE_CONNECTED:    state_str = "CONNECTED";    break;
    case NETWORK_STATE_CONNECTING:   state_str = "CONNECTING";   break;
    case NETWORK_STATE_DISCONNECTED: state_str = "DISCONNECTED"; break;
    default:                         state_str = "IDLE";         break;
    }
    lv_label_set_text(s_lbl_wifi_state, state_str);

    network_get_ssid(buf, sizeof(buf));
    lv_label_set_text(s_lbl_ssid, buf[0] ? buf : "-");
    network_get_ip(buf, sizeof(buf));
    lv_label_set_text(s_lbl_ip, buf[0] ? buf : "-");

    int rssi = network_get_rssi();
    if (rssi != 0) {
        lv_label_set_text_fmt(s_lbl_rssi, "%d dBm  %s",
                              rssi, rssi_quality_label(rssi));
    } else {
        lv_label_set_text(s_lbl_rssi, "-");
    }
    update_rssi_bars(rssi);

    network_get_mac(buf, sizeof(buf));
    lv_label_set_text(s_lbl_mac, buf[0] ? buf : "-");

    /* Rail server block. */
    if (s_rail_link) {
        lv_label_set_text(s_lbl_srv_state, "online");
        lv_obj_set_style_text_color(s_lbl_srv_state, lv_color_hex(COL_OK), 0);
        if (s_rail.connected && s_rail.position_valid) {
            lv_label_set_text_fmt(s_lbl_rail_pos, "%.2f mm  %s",
                                  s_rail.position_mm,
                                  s_rail.state[0] ? s_rail.state : "");
        } else {
            lv_label_set_text(s_lbl_rail_pos, "rail offline");
        }
        lv_label_set_text_fmt(s_lbl_rail_age, "%d s ago", s_rail.age_s);
    } else {
        lv_label_set_text(s_lbl_srv_state, s_rail_reason);
        lv_obj_set_style_text_color(s_lbl_srv_state, lv_color_hex(COL_BAD), 0);
        lv_label_set_text(s_lbl_rail_pos, "-");
        lv_label_set_text(s_lbl_rail_age, "-");
    }
}

static void build_status_tab(lv_obj_t *tab)
{
    lv_obj_set_style_pad_all(tab, 8, 0);
    lv_obj_set_style_bg_color(tab, lv_color_hex(COL_BG), 0);
    lv_obj_set_style_bg_opa(tab, LV_OPA_COVER, 0);
    lv_obj_clear_flag(tab, LV_OBJ_FLAG_SCROLLABLE);

    const int row_h = 19;
    int y = 0;

    add_kv_row(tab, 0, y, "Wi-Fi", &s_lbl_wifi_state); y += row_h;
    add_kv_row(tab, 0, y, "SSID",  &s_lbl_ssid);       y += row_h;
    add_kv_row(tab, 0, y, "IP",    &s_lbl_ip);         y += row_h;
    add_kv_row(tab, 0, y, "RSSI",  &s_lbl_rssi);
    build_rssi_bars(tab, 240, y + 17);                 y += row_h;
    add_kv_row(tab, 0, y, "MAC",   &s_lbl_mac);        y += row_h + 4;

    lv_obj_t *sep = lv_obj_create(tab);
    lv_obj_remove_style_all(sep);
    lv_obj_set_size(sep, SCR_W - 24, 1);
    lv_obj_set_pos(sep, 0, y);
    lv_obj_set_style_bg_color(sep, lv_color_hex(0x3D3D3D), 0);
    lv_obj_set_style_bg_opa(sep, LV_OPA_COVER, 0);
    y += 6;

    add_kv_row(tab, 0, y, "Server",   &s_lbl_srv_state); y += row_h;
    add_kv_row(tab, 0, y, "Position", &s_lbl_rail_pos);  y += row_h;
    add_kv_row(tab, 0, y, "Updated",  &s_lbl_rail_age);

    lv_timer_create(status_refresh_cb, 1000, NULL);
    status_refresh_cb(NULL);
}

/* ---------------------- Move tab (X/Z placeholder) ---------------------- */

static void plot_grid_draw_cb(lv_event_t *e)
{
    lv_layer_t *layer = lv_event_get_layer(e);
    lv_obj_t   *obj   = lv_event_get_target(e);

    lv_area_t a;
    lv_obj_get_coords(obj, &a);

    lv_draw_line_dsc_t line;
    lv_draw_line_dsc_init(&line);
    line.width = 1;
    line.opa   = LV_OPA_COVER;

    for (int mm = GRID_STEP_MM; mm < MAX_TRAVEL_MM; mm += GRID_STEP_MM) {
        bool major = (mm % GRID_MAJOR_MM == 0);
        line.color = lv_color_hex(major ? 0x4D5278 : 0x2D3050);
        int px = mm * PLOT_SIZE / MAX_TRAVEL_MM;
        line.p1.x = a.x1 + px; line.p1.y = a.y1;
        line.p2.x = a.x1 + px; line.p2.y = a.y2;
        lv_draw_line(layer, &line);
        line.p1.x = a.x1; line.p1.y = a.y1 + px;
        line.p2.x = a.x2; line.p2.y = a.y1 + px;
        lv_draw_line(layer, &line);
    }
}

static void refresh_move_widgets(void)
{
    int px_x = PLOT_SIZE - s_target_x_mm * PLOT_SIZE / MAX_TRAVEL_MM;
    int px_y = s_target_z_mm * PLOT_SIZE / MAX_TRAVEL_MM;

    lv_obj_set_pos(s_v_line, PLOT_X_OFFSET + px_x - 1, PLOT_Y_OFFSET);
    lv_obj_set_pos(s_h_line, PLOT_X_OFFSET, PLOT_Y_OFFSET + px_y - 1);
    lv_obj_set_pos(s_marker, PLOT_X_OFFSET + px_x - MARKER_R,
                   PLOT_Y_OFFSET + px_y - MARKER_R);

    lv_label_set_text_fmt(s_lbl_target_x, "X: %3d mm", s_target_x_mm);
    lv_label_set_text_fmt(s_lbl_target_z, "Z: %3d mm", s_target_z_mm);
}

static void plot_event_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    if (code != LV_EVENT_PRESSED && code != LV_EVENT_PRESSING) {
        return;
    }
    lv_indev_t *indev = lv_event_get_indev(e);
    if (!indev) indev = lv_indev_active();
    if (!indev) return;

    lv_point_t pt = {0, 0};
    lv_indev_get_point(indev, &pt);

    lv_area_t area;
    lv_obj_get_coords(s_plot, &area);
    int px = pt.x - area.x1;
    int py = pt.y - area.y1;
    if (px < 0) px = 0;
    if (px > PLOT_SIZE) px = PLOT_SIZE;
    if (py < 0) py = 0;
    if (py > PLOT_SIZE) py = PLOT_SIZE;

    s_target_x_mm = (PLOT_SIZE - px) * MAX_TRAVEL_MM / PLOT_SIZE;
    s_target_z_mm = py * MAX_TRAVEL_MM / PLOT_SIZE;
    refresh_move_widgets();
}

/* X/Z move is reserved for the future pipette station; the picker updates
 * its readout but there is no motor backend to drive yet. */
static void confirm_event_cb(lv_event_t *e)
{
    (void)e;
}

static void build_move_tab(lv_obj_t *tab)
{
    lv_obj_set_style_pad_all(tab, 0, 0);
    lv_obj_set_style_bg_color(tab, lv_color_hex(COL_BG), 0);
    lv_obj_set_style_bg_opa(tab, LV_OPA_COVER, 0);
    lv_obj_clear_flag(tab, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *div = lv_obj_create(tab);
    lv_obj_remove_style_all(div);
    lv_obj_set_pos(div, LEFT_W, 0);
    lv_obj_set_size(div, 4, CONTENT_H);
    lv_obj_set_style_bg_color(div, lv_color_hex(0x3D3D3D), 0);
    lv_obj_set_style_bg_opa(div, LV_OPA_COVER, 0);

    s_plot = lv_obj_create(tab);
    lv_obj_remove_style_all(s_plot);
    lv_obj_set_size(s_plot, PLOT_SIZE, PLOT_SIZE);
    lv_obj_set_pos(s_plot, PLOT_X_OFFSET, PLOT_Y_OFFSET);
    lv_obj_set_style_bg_color(s_plot, lv_color_hex(0x22253A), 0);
    lv_obj_set_style_bg_opa(s_plot, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(s_plot, lv_color_hex(0x4D5278), 0);
    lv_obj_set_style_border_width(s_plot, 1, 0);
    lv_obj_set_style_radius(s_plot, 0, 0);
    lv_obj_add_flag(s_plot, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(s_plot, LV_OBJ_FLAG_GESTURE_BUBBLE);
    lv_obj_clear_flag(s_plot, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_event_cb(s_plot, plot_grid_draw_cb, LV_EVENT_DRAW_MAIN, NULL);

    s_v_line = lv_obj_create(tab);
    lv_obj_remove_style_all(s_v_line);
    lv_obj_set_size(s_v_line, 2, PLOT_SIZE);
    lv_obj_set_style_bg_color(s_v_line, lv_color_hex(COL_Z), 0);
    lv_obj_set_style_bg_opa(s_v_line, LV_OPA_COVER, 0);
    lv_obj_add_flag(s_v_line, LV_OBJ_FLAG_IGNORE_LAYOUT);

    s_h_line = lv_obj_create(tab);
    lv_obj_remove_style_all(s_h_line);
    lv_obj_set_size(s_h_line, PLOT_SIZE, 2);
    lv_obj_set_style_bg_color(s_h_line, lv_color_hex(COL_X), 0);
    lv_obj_set_style_bg_opa(s_h_line, LV_OPA_COVER, 0);
    lv_obj_add_flag(s_h_line, LV_OBJ_FLAG_IGNORE_LAYOUT);

    s_marker = lv_obj_create(tab);
    lv_obj_remove_style_all(s_marker);
    lv_obj_set_size(s_marker, MARKER_R * 2, MARKER_R * 2);
    lv_obj_set_style_radius(s_marker, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(s_marker, lv_color_hex(COL_TEXT), 0);
    lv_obj_set_style_bg_opa(s_marker, LV_OPA_COVER, 0);
    lv_obj_add_flag(s_marker, LV_OBJ_FLAG_IGNORE_LAYOUT);

    lv_obj_add_event_cb(s_plot, plot_event_cb, LV_EVENT_PRESSED,  NULL);
    lv_obj_add_event_cb(s_plot, plot_event_cb, LV_EVENT_PRESSING, NULL);

    const int below_y = PLOT_Y_OFFSET + PLOT_SIZE + 6;

    s_lbl_target_x = lv_label_create(tab);
    lv_obj_set_style_text_color(s_lbl_target_x, lv_color_hex(COL_X), 0);
    lv_obj_set_style_text_font(s_lbl_target_x, &lv_font_montserrat_18, 0);
    lv_obj_set_pos(s_lbl_target_x, 10, below_y);

    s_lbl_target_z = lv_label_create(tab);
    lv_obj_set_style_text_color(s_lbl_target_z, lv_color_hex(COL_Z), 0);
    lv_obj_set_style_text_font(s_lbl_target_z, &lv_font_montserrat_18, 0);
    lv_obj_set_pos(s_lbl_target_z, 10, below_y + 18);

    lv_obj_t *confirm_btn = lv_button_create(tab);
    lv_obj_set_size(confirm_btn, 85, 36);
    lv_obj_set_pos(confirm_btn, 115, below_y + 2);
    lv_obj_set_style_bg_color(confirm_btn, lv_color_hex(COL_OK), 0);
    lv_obj_set_style_bg_color(confirm_btn,
        lv_color_hex(COL_OK >> 1 & 0x7F7F7F), LV_STATE_PRESSED);
    lv_obj_set_style_radius(confirm_btn, 8, 0);
    lv_obj_set_style_border_width(confirm_btn, 0, 0);
    lv_obj_set_style_shadow_width(confirm_btn, 0, 0);
    lv_obj_add_event_cb(confirm_btn, confirm_event_cb, LV_EVENT_CLICKED, NULL);

    lv_obj_t *confirm_lbl = lv_label_create(confirm_btn);
    lv_label_set_text(confirm_lbl, LV_SYMBOL_OK "  Move");
    lv_obj_set_style_text_color(confirm_lbl, lv_color_hex(COL_TEXT), 0);
    lv_obj_set_style_text_font(confirm_lbl, &lv_font_montserrat_18, 0);
    lv_obj_center(confirm_lbl);

    lv_obj_t *pip = lv_obj_create(tab);
    lv_obj_remove_style_all(pip);
    lv_obj_set_pos(pip, RIGHT_X, 6);
    lv_obj_set_size(pip, RIGHT_W, CONTENT_H - 12);
    lv_obj_set_style_bg_color(pip, lv_color_hex(0x22253A), 0);
    lv_obj_set_style_bg_opa(pip, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(pip, lv_color_hex(0x3D3D3D), 0);
    lv_obj_set_style_border_width(pip, 1, 0);
    lv_obj_set_style_radius(pip, 8, 0);

    lv_obj_t *pip_lbl = lv_label_create(pip);
    lv_label_set_text(pip_lbl, "Pipette\n(TBD)");
    lv_obj_set_style_text_align(pip_lbl, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(pip_lbl, lv_color_hex(COL_TEXT_DIM), 0);
    lv_obj_set_style_text_font(pip_lbl, &lv_font_montserrat_18, 0);
    lv_obj_center(pip_lbl);

    refresh_move_widgets();
}

/* ---------------------- public API ---------------------- */

void ui_create(void)
{
    lv_obj_t *scr = lv_scr_act();
    lv_obj_set_style_bg_color(scr, lv_color_hex(COL_BG), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);

    lv_obj_t *tv = lv_tabview_create(scr);
    lv_tabview_set_tab_bar_position(tv, LV_DIR_TOP);
    lv_tabview_set_tab_bar_size(tv, TAB_BAR_H);
    lv_obj_set_style_bg_color(tv, lv_color_hex(COL_BG), 0);
    lv_obj_set_style_text_color(tv, lv_color_hex(COL_TEXT), 0);
    lv_obj_clear_flag(lv_tabview_get_content(tv), LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *tab_move = lv_tabview_add_tab(tv, "Move Control");
    lv_obj_t *tab_ctrl = lv_tabview_add_tab(tv, "Jog Control");
    lv_obj_t *tab_stat = lv_tabview_add_tab(tv, "Status");

    build_move_tab(tab_move);
    build_control_tab(tab_ctrl);
    build_status_tab(tab_stat);

    lv_tabview_set_active(tv, 1, LV_ANIM_OFF);
}

void ui_set_status(const ui_status_t *st)
{
    if (!st) {
        return;
    }
    s_rail = *st;
    s_rail_link = true;
}

void ui_set_offline(const char *reason)
{
    s_rail_link = false;
    snprintf(s_rail_reason, sizeof(s_rail_reason), "%s",
             reason ? reason : "offline");
}
