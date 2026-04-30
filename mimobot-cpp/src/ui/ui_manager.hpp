#ifndef UI_MANAGER_HPP
#define UI_MANAGER_HPP

#include "lvgl/lvgl.h"
#include <mutex>

extern std::mutex lvgl_mutex;

/* Initialize the dashboard (TileView Navigation) */
void ui_init();

/* Hardware Dashboard Updater */
void ui_update_telemetry(int cpu, int gpu, const char* ram, int disk);

/* Dynamic Swipe Left State Updater */
void ui_set_dynamic_mode(bool is_music, bool is_discord);

/* Update the music labels from the background thread */
void ui_update_song(const char * title, const char * artist);

/* Show a sliding notification pop-up or add to Notif Tile */
void ui_show_notif(const char * app, const char * msg);

/* Show a calendar reminder (Green accent) */
void ui_show_reminder(const char * title, const char * time);

/* Update a button with a Base64 icon */
void ui_update_icon(int slot, const char * base64_png);

/* Visualizer & Pomodoro */
void ui_update_viz(int * values);
void ui_start_pomo(int minutes);

#endif // UI_MANAGER_HPP
