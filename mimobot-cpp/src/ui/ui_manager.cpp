#include "ui_manager.hpp"
#include "audio/music_controller.hpp"
#include <stdio.h>

/* UI Globals */
static lv_obj_t * tv;
static lv_obj_t * eye_left;
static lv_obj_t * eye_right;
static lv_obj_t * mouth;
static lv_obj_t * deck_btns[6];

/* Hardware Dash Globals */
static lv_obj_t * cpu_label;
static lv_obj_t * gpu_label;
static lv_obj_t * ram_label;
static lv_obj_t * disk_label;

/* Notification Feed Globals */
#define MAX_NOTIFS 5
static lv_obj_t * notif_list   = NULL;  // scrollable container
static int        notif_count  = 0;

/* Moods */
typedef enum {
    MOCHI_HAPPY,
    MOCHI_SLEEPING,
    MOCHI_SURPRISED
} mochi_mood_t;

static mochi_mood_t current_mood = MOCHI_HAPPY;
static uint32_t last_activity_time = 0;

/* Dynamic Tile Globals */
static lv_obj_t * dynamic_container;
static lv_obj_t * music_layer;
static lv_obj_t * discord_layer;
static lv_obj_t * song_label;
static lv_obj_t * artist_label;

/* Visualizer Globals */
static lv_obj_t * viz_bars[10];
static int viz_values[10] = {0};

/* Pomodoro Globals */
static lv_obj_t * pomo_overlay = NULL;
static lv_obj_t * pomo_label = NULL;
static int pomo_seconds = 0;

/* Animation Timer Callback (Blinking and Breathing) */
static void animation_timer_cb(lv_timer_t * timer) {
    static bool blinking = false;
    static int breath_val = 0;
    static bool breath_up = true;

    // Check for inactivity (Sleep after 5 mins)
    if (lv_tick_get() - last_activity_time > 300000 && current_mood != MOCHI_SLEEPING) {
        current_mood = MOCHI_SLEEPING;
        lv_obj_set_height(eye_left, 5);
        lv_obj_set_height(eye_right, 5);
    }

    if (current_mood == MOCHI_SLEEPING) {
        // Slow "sleeping" breath
        if (breath_up) breath_val += 1; else breath_val -= 1;
        if (breath_val > 10) breath_up = false;
        if (breath_val < 0) breath_up = true;
        lv_obj_set_y(mouth, 60 + (breath_val / 2));
        return; // No blinking while asleep
    }

    // Normal Mood Logic
    if (lv_tick_get() % 3000 < 100) { // Blink every 3s
        lv_obj_set_height(eye_left, 5);
        lv_obj_set_height(eye_right, 5);
    } else {
        lv_obj_set_height(eye_left, 70);
        lv_obj_set_height(eye_right, 70);
    }

    // Breathing mouth
    if (breath_up) breath_val += 2; else breath_val -= 2;
    if (breath_val > 20) breath_up = false;
    if (breath_val < 0) breath_up = true;
    lv_obj_set_width(mouth, 60 + breath_val);

    // Update Visualizer Bars (smooth decay)
    for(int i = 0; i < 10; i++) {
        if(viz_values[i] > 2) viz_values[i] -= 2; else viz_values[i] = 0;
        lv_obj_set_height(viz_bars[i], 5 + viz_values[i]);
    }

    // Update Pomodoro
    if(pomo_seconds > 0) {
        static uint32_t last_pomo_tick = 0;
        if(lv_tick_get() - last_pomo_tick > 1000) {
            pomo_seconds--;
            last_pomo_tick = lv_tick_get();
            if(pomo_label) lv_label_set_text_fmt(pomo_label, "%02d:%02d", pomo_seconds/60, pomo_seconds%60);
            if(pomo_seconds == 0) {
                lv_obj_add_flag(pomo_overlay, LV_OBJ_FLAG_HIDDEN);
                ui_show_notif("Pomodoro", "Time's up! Take a break.");
            }
        }
    }
}

static void tv_event_cb(lv_event_t * e) {
    last_activity_time = lv_tick_get();
    if (current_mood == MOCHI_SLEEPING) {
        current_mood = MOCHI_HAPPY;
        // Visual "Wake up" feedback
        lv_obj_set_height(eye_left, 80);
        lv_obj_set_height(eye_right, 80);
    }
}

void ui_init() {
    /* Create the core OS TileView */
    tv = lv_tileview_create(lv_scr_act());
    lv_obj_set_style_bg_color(tv, lv_color_hex(0x0A0A0A), 0);
    lv_obj_add_event_cb(tv, tv_event_cb, LV_EVENT_ALL, NULL);
    last_activity_time = lv_tick_get();

    /* ==========================================
     * 1. CENTER TILE (2, 1): Dasai Mochi Face 
     * ========================================== */
    lv_obj_t * tile_face = lv_tileview_add_tile(tv, 2, 1, LV_DIR_ALL);
    
    static lv_style_t style_eye;
    lv_style_init(&style_eye);
    lv_style_set_bg_color(&style_eye, lv_color_white());
    lv_style_set_radius(&style_eye, 20);
    lv_style_set_shadow_width(&style_eye, 15);
    lv_style_set_shadow_color(&style_eye, lv_color_white());
    lv_style_set_shadow_opa(&style_eye, LV_OPA_50);

    eye_left = lv_obj_create(tile_face);
    lv_obj_add_style(eye_left, &style_eye, 0);
    lv_obj_set_size(eye_left, 35, 70);
    lv_obj_align(eye_left, LV_ALIGN_CENTER, -60, -20);

    eye_right = lv_obj_create(tile_face);
    lv_obj_add_style(eye_right, &style_eye, 0);
    lv_obj_set_size(eye_right, 35, 70);
    lv_obj_align(eye_right, LV_ALIGN_CENTER, 60, -20);

    mouth = lv_obj_create(tile_face);
    lv_obj_set_size(mouth, 60, 5);
    lv_obj_set_style_bg_color(mouth, lv_color_white(), 0);
    lv_obj_align(mouth, LV_ALIGN_CENTER, 0, 60);

    // Visualizer Bars
    for(int i = 0; i < 10; i++) {
        viz_bars[i] = lv_obj_create(tile_face);
        lv_obj_set_size(viz_bars[i], 12, 5);
        lv_obj_set_style_bg_color(viz_bars[i], lv_color_hex(0x00A3FF), 0);
        lv_obj_set_style_border_width(viz_bars[i], 0, 0);
        lv_obj_set_style_radius(viz_bars[i], 5, 0);
        lv_obj_align(viz_bars[i], LV_ALIGN_BOTTOM_MID, -75 + (i * 17), -10);
    }

    // Pomodoro Overlay
    pomo_overlay = lv_obj_create(tile_face);
    lv_obj_set_size(pomo_overlay, 100, 40);
    lv_obj_align(pomo_overlay, LV_ALIGN_TOP_RIGHT, -10, 10);
    lv_obj_set_style_bg_color(pomo_overlay, lv_color_hex(0xFF4B4B), 0);
    lv_obj_set_style_border_width(pomo_overlay, 0, 0);
    lv_obj_set_style_radius(pomo_overlay, 10, 0);
    pomo_label = lv_label_create(pomo_overlay);
    lv_obj_center(pomo_label);
    lv_label_set_text(pomo_label, "25:00");
    lv_obj_add_flag(pomo_overlay, LV_OBJ_FLAG_HIDDEN);

    lv_timer_create(animation_timer_cb, 50, NULL); // Fast 20fps for smooth breath

    /* ==========================================
     * 2. BOTTOM TILE (2, 2): Hardware Dashboard 
     * ========================================== */
    lv_obj_t * tile_hw = lv_tileview_add_tile(tv, 2, 2, LV_DIR_TOP);
    
    lv_obj_t * hw_title = lv_label_create(tile_hw);
    lv_label_set_text(hw_title, "Hardware Stats");
    lv_obj_set_style_text_color(hw_title, lv_color_hex(0x00A3FF), 0);
    lv_obj_align(hw_title, LV_ALIGN_TOP_MID, 0, 20);

    lv_obj_t * hw_grid = lv_obj_create(tile_hw);
    lv_obj_set_size(hw_grid, LV_PCT(100), LV_PCT(80));
    lv_obj_align(hw_grid, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_opa(hw_grid, 0, 0);
    lv_obj_set_style_border_width(hw_grid, 0, 0);
    lv_obj_set_flex_flow(hw_grid, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(hw_grid, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_gap(hw_grid, 10, 0);

    // CPU Gauge
    lv_obj_t * cpu_card = lv_obj_create(hw_grid);
    lv_obj_set_size(cpu_card, 140, 80);
    lv_obj_set_style_bg_color(cpu_card, lv_color_hex(0x151515), 0);
    lv_obj_set_style_border_width(cpu_card, 0, 0);
    lv_label_set_text(lv_label_create(cpu_card), "CPU");
    cpu_label = lv_label_create(cpu_card);
    lv_label_set_text(cpu_label, "0%");
    lv_obj_set_style_text_color(cpu_label, lv_color_white(), 0);
    lv_obj_align(cpu_label, LV_ALIGN_CENTER, 0, 10);

    // GPU Gauge
    lv_obj_t * gpu_card = lv_obj_create(hw_grid);
    lv_obj_set_size(gpu_card, 140, 80);
    lv_obj_set_style_bg_color(gpu_card, lv_color_hex(0x151515), 0);
    lv_obj_set_style_border_width(gpu_card, 0, 0);
    lv_label_set_text(lv_label_create(gpu_card), "GPU");
    gpu_label = lv_label_create(gpu_card);
    lv_label_set_text(gpu_label, "0%");
    lv_obj_set_style_text_color(gpu_label, lv_color_white(), 0);
    lv_obj_align(gpu_label, LV_ALIGN_CENTER, 0, 10);

    // RAM Gauge
    lv_obj_t * ram_card = lv_obj_create(hw_grid);
    lv_obj_set_size(ram_card, 140, 80);
    lv_obj_set_style_bg_color(ram_card, lv_color_hex(0x151515), 0);
    lv_obj_set_style_border_width(ram_card, 0, 0);
    lv_label_set_text(lv_label_create(ram_card), "RAM");
    ram_label = lv_label_create(ram_card);
    lv_label_set_text(ram_label, "0 GB");
    lv_obj_set_style_text_color(ram_label, lv_color_white(), 0);
    lv_obj_align(ram_label, LV_ALIGN_CENTER, 0, 10);

    // DISK Gauge
    lv_obj_t * disk_card = lv_obj_create(hw_grid);
    lv_obj_set_size(disk_card, 140, 80);
    lv_obj_set_style_bg_color(disk_card, lv_color_hex(0x151515), 0);
    lv_obj_set_style_border_width(disk_card, 0, 0);
    lv_label_set_text(lv_label_create(disk_card), "DISK");
    disk_label = lv_label_create(disk_card);
    lv_label_set_text(disk_label, "0%");
    lv_obj_set_style_text_color(disk_label, lv_color_white(), 0);
    lv_obj_align(disk_label, LV_ALIGN_CENTER, 0, 10);

    /* ==========================================
     * 3. LEFT TILE (1, 1): Stream Deck 
     * ========================================== */
    lv_obj_t * tile_deck = lv_tileview_add_tile(tv, 1, 1, LV_DIR_HOR);
    
    lv_obj_t * deck_grid = lv_obj_create(tile_deck);
    lv_obj_set_size(deck_grid, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_opa(deck_grid, 0, 0);
    lv_obj_set_style_border_width(deck_grid, 0, 0);
    lv_obj_set_flex_flow(deck_grid, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(deck_grid, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_gap(deck_grid, 15, 0);

    for(int i = 0; i < 6; i++) {
        lv_obj_t * btn = lv_btn_create(deck_grid);
        lv_obj_set_size(btn, 85, 85);
        lv_obj_t * label = lv_label_create(btn);
        lv_label_set_text_fmt(label, "App %d", i+1);
        lv_obj_center(label);
        deck_btns[i] = btn;
    }

    /* ==========================================
     * 4. FAR LEFT TILE (0, 1): Features Menu 
     * ========================================== */
    lv_obj_t * tile_features = lv_tileview_add_tile(tv, 0, 1, LV_DIR_RIGHT);
    
    lv_obj_t * features_title = lv_label_create(tile_features);
    lv_label_set_text(features_title, "App Features");
    lv_obj_set_style_text_color(features_title, lv_color_hex(0x00A3FF), 0);
    lv_obj_align(features_title, LV_ALIGN_TOP_MID, 0, 20);

    lv_obj_t * f_list = lv_obj_create(tile_features);
    lv_obj_set_size(f_list, LV_PCT(100), LV_PCT(80));
    lv_obj_align(f_list, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_opa(f_list, 0, 0);
    lv_obj_set_style_border_width(f_list, 0, 0);
    lv_obj_set_flex_flow(f_list, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_gap(f_list, 10, 0);

    for(int i = 0; i < 4; i++) {
        lv_obj_t * btn = lv_btn_create(f_list);
        lv_obj_set_width(btn, LV_PCT(90));
        lv_obj_t * label = lv_label_create(btn);
        lv_label_set_text_fmt(label, "Feature %d", i+1);
        lv_obj_center(label);
    }

    /* ==========================================
     * 5. TOP TILE (2, 0): Notification Feed
     * ========================================== */
    lv_obj_t * tile_notif = lv_tileview_add_tile(tv, 2, 0, LV_DIR_BOTTOM);

    // Header bar
    lv_obj_t * notif_hdr = lv_label_create(tile_notif);
    lv_label_set_text(notif_hdr, "Notifications");
    lv_obj_set_style_text_color(notif_hdr, lv_color_hex(0x00A3FF), 0);
    lv_obj_align(notif_hdr, LV_ALIGN_TOP_MID, 0, 12);

    // Scrollable list that fills the rest of the tile
    notif_list = lv_obj_create(tile_notif);
    lv_obj_set_size(notif_list, LV_PCT(100), LV_PCT(88));
    lv_obj_align(notif_list, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_color(notif_list, lv_color_hex(0x0A0A0A), 0);
    lv_obj_set_style_border_width(notif_list, 0, 0);
    lv_obj_set_style_pad_all(notif_list, 8, 0);
    lv_obj_set_style_pad_gap(notif_list, 8, 0);
    lv_obj_set_flex_flow(notif_list, LV_FLEX_FLOW_COLUMN);
    // Allow vertical scroll; hide scrollbar
    lv_obj_set_scroll_dir(notif_list, LV_DIR_VER);
    lv_obj_set_scrollbar_mode(notif_list, LV_SCROLLBAR_MODE_OFF);

    // "No notifications yet" placeholder
    lv_obj_t * notif_empty = lv_label_create(notif_list);
    lv_label_set_text(notif_empty, "No notifications yet");
    lv_obj_set_style_text_color(notif_empty, lv_color_hex(0x444444), 0);
    lv_obj_center(notif_empty);

    /* ==========================================
     * 6. RIGHT TILE (3, 1): Dynamic Media/Discord
     * ========================================== */
    lv_obj_t * tile_dynamic = lv_tileview_add_tile(tv, 3, 1, LV_DIR_LEFT);
    
    dynamic_container = lv_obj_create(tile_dynamic);
    lv_obj_set_size(dynamic_container, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_opa(dynamic_container, 0, 0);
    lv_obj_set_style_border_width(dynamic_container, 0, 0);

    // --- Media Layer ---
    music_layer = lv_obj_create(dynamic_container);
    lv_obj_set_size(music_layer, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_opa(music_layer, 0, 0);
    lv_obj_set_style_border_width(music_layer, 0, 0);
    
    song_label = lv_label_create(music_layer);
    lv_label_set_text(song_label, "No Song Playing");
    lv_obj_align(song_label, LV_ALIGN_CENTER, 0, -30);
    
    artist_label = lv_label_create(music_layer);
    lv_label_set_text(artist_label, "Unknown Artist");
    lv_obj_align(artist_label, LV_ALIGN_CENTER, 0, 0);

    lv_obj_t * controls = lv_obj_create(music_layer);
    lv_obj_set_size(controls, LV_PCT(80), 60);
    lv_obj_align(controls, LV_ALIGN_BOTTOM_MID, 0, -20);
    lv_obj_set_flex_flow(controls, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(controls, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    
    lv_label_set_text(lv_label_create(lv_btn_create(controls)), LV_SYMBOL_PREV);
    lv_label_set_text(lv_label_create(lv_btn_create(controls)), LV_SYMBOL_PLAY);
    lv_label_set_text(lv_label_create(lv_btn_create(controls)), LV_SYMBOL_NEXT);

    // --- Discord Layer ---
    discord_layer = lv_obj_create(dynamic_container);
    lv_obj_set_size(discord_layer, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_opa(discord_layer, 0, 0);
    lv_obj_set_style_border_width(discord_layer, 0, 0);
    lv_obj_add_flag(discord_layer, LV_OBJ_FLAG_HIDDEN); // Hidden by default

    lv_obj_t * d_title = lv_label_create(discord_layer);
    lv_label_set_text(d_title, "Discord Voice Hub");
    lv_obj_set_style_text_color(d_title, lv_color_hex(0x5865F2), 0);
    lv_obj_align(d_title, LV_ALIGN_TOP_MID, 0, 20);

    /* Jump to Center Tile on startup */
    lv_obj_set_tile_id(tv, 2, 1, LV_ANIM_OFF);
}

void ui_update_telemetry(int cpu, int gpu, const char* ram, int disk) {
    std::lock_guard<std::mutex> lock(lvgl_mutex);
    if(cpu_label) lv_label_set_text_fmt(cpu_label, "%d%%", cpu);
    if(gpu_label) lv_label_set_text_fmt(gpu_label, "%d%%", gpu);
    if(disk_label) lv_label_set_text_fmt(disk_label, "%d%%", disk);
    if(ram_label) lv_label_set_text(ram_label, ram);
}

void ui_set_dynamic_mode(bool is_music, bool is_discord) {
    std::lock_guard<std::mutex> lock(lvgl_mutex);
    if(is_discord) {
        lv_obj_add_flag(music_layer, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(discord_layer, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(discord_layer, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(music_layer, LV_OBJ_FLAG_HIDDEN);
    }
}

void ui_update_viz(int * values) {
    std::lock_guard<std::mutex> lock(lvgl_mutex);
    for(int i = 0; i < 10; i++) {
        if(values[i] > viz_values[i]) viz_values[i] = values[i];
    }
}

void ui_start_pomo(int minutes) {
    std::lock_guard<std::mutex> lock(lvgl_mutex);
    pomo_seconds = minutes * 60;
    if(pomo_overlay) lv_obj_clear_flag(pomo_overlay, LV_OBJ_FLAG_HIDDEN);
}

void ui_update_song(const char * title, const char * artist) {
    std::lock_guard<std::mutex> lock(lvgl_mutex);
    if(song_label) lv_label_set_text(song_label, title);
    if(artist_label) lv_label_set_text(artist_label, artist);
}

void ui_show_notif(const char * app, const char * msg) {
    std::lock_guard<std::mutex> lock(lvgl_mutex);
    if(!notif_list) return;

    // If this is the first real notif, clear the placeholder
    if(notif_count == 0) {
        lv_obj_clean(notif_list);
    }

    // Ring buffer: remove oldest card when we exceed MAX_NOTIFS
    if(notif_count >= MAX_NOTIFS) {
        lv_obj_t * first = lv_obj_get_child(notif_list, 0);
        if(first) lv_obj_del(first);
        notif_count--;
    }

    // ── Card container ──────────────────────────────────────────────────────
    lv_obj_t * card = lv_obj_create(notif_list);
    lv_obj_set_width(card, LV_PCT(100));
    lv_obj_set_height(card, LV_SIZE_CONTENT);   // auto-height wraps text
    lv_obj_set_style_bg_color(card, lv_color_hex(0x1A1A1A), 0);
    lv_obj_set_style_border_width(card, 0, 0);
    lv_obj_set_style_radius(card, 12, 0);
    lv_obj_set_style_pad_all(card, 12, 0);
    lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_gap(card, 6, 0);
    // Left accent bar
    lv_obj_set_style_border_color(card, lv_color_hex(0x00A3FF), 0);
    lv_obj_set_style_border_width(card, 3, 0);
    lv_obj_set_style_border_side(card, LV_BORDER_SIDE_LEFT, 0);

    // ── App name (header) ───────────────────────────────────────────────────
    lv_obj_t * lbl_app = lv_label_create(card);
    lv_label_set_text(lbl_app, app);
    lv_obj_set_style_text_color(lbl_app, lv_color_hex(0x00A3FF), 0);
    lv_obj_set_width(lbl_app, LV_PCT(100));

    // ── Message body (word-wrapped) ─────────────────────────────────────────
    lv_obj_t * lbl_msg = lv_label_create(card);
    lv_label_set_text(lbl_msg, msg);
    lv_label_set_long_mode(lbl_msg, LV_LABEL_LONG_WRAP); // key: wrap not scroll
    lv_obj_set_width(lbl_msg, LV_PCT(100));
    lv_obj_set_style_text_color(lbl_msg, lv_color_hex(0xDDDDDD), 0);

    notif_count++;

    // Auto-scroll to the newest card at the bottom
    lv_obj_scroll_to_y(notif_list, LV_COORD_MAX, LV_ANIM_ON);
}

void ui_show_reminder(const char * title, const char * time) {
    std::lock_guard<std::mutex> lock(lvgl_mutex);
    if(!notif_list) return;

    if(notif_count == 0) lv_obj_clean(notif_list);

    if(notif_count >= MAX_NOTIFS) {
        lv_obj_t * first = lv_obj_get_child(notif_list, 0);
        if(first) lv_obj_del(first);
        notif_count--;
    }

    lv_obj_t * card = lv_obj_create(notif_list);
    lv_obj_set_width(card, LV_PCT(100));
    lv_obj_set_height(card, LV_SIZE_CONTENT);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x1A1A1A), 0);
    lv_obj_set_style_border_width(card, 0, 0);
    lv_obj_set_style_radius(card, 12, 0);
    lv_obj_set_style_pad_all(card, 12, 0);
    lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_gap(card, 6, 0);
    
    // Green accent for calendar
    lv_obj_set_style_border_color(card, lv_color_hex(0x2ECC71), 0);
    lv_obj_set_style_border_width(card, 3, 0);
    lv_obj_set_style_border_side(card, LV_BORDER_SIDE_LEFT, 0);

    lv_obj_t * lbl_hdr = lv_label_create(card);
    lv_label_set_text(lbl_hdr, "Calendar Event");
    lv_obj_set_style_text_color(lbl_hdr, lv_color_hex(0x2ECC71), 0);

    lv_obj_t * lbl_title = lv_label_create(card);
    lv_label_set_text_fmt(lbl_title, "%s", title);
    lv_obj_set_style_text_color(lbl_title, lv_color_white(), 0);
    lv_label_set_long_mode(lbl_title, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(lbl_title, LV_PCT(100));

    lv_obj_t * lbl_time = lv_label_create(card);
    lv_label_set_text_fmt(lbl_time, "Time: %s", time);
    lv_obj_set_style_text_color(lbl_time, lv_color_hex(0x888888), 0);

    notif_count++;
    lv_obj_scroll_to_y(notif_list, LV_COORD_MAX, LV_ANIM_ON);
}
