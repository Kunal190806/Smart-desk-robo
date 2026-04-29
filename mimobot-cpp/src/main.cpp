#include "lvgl/lvgl.h"
#include "ui/ui_manager.hpp"
#include "audio/music_controller.hpp"
#include "network/network_manager.hpp"
#include <stdio.h>
#include <thread>
#include <chrono>

/* 
 * Mimobot Pro – C++/LVGL Main Entry
 * This file initializes the LVGL engine and sets up the Pro Dashboard.
 */

std::mutex lvgl_mutex;

int main(int argc, char **argv) {
    /* 1. Initialize LVGL */
    lv_init();

    /* 2. Initialize Display and Input Drivers (SDL for testing) */
    // lv_sdl_window_create(320, 240);
    // lv_sdl_mouse_create();

    /* 3. Create our Pro Dashboard */
    ui_init();

    /* 4. Initialize Music Controller */
    if(music_init()) {
        std::thread(music_update_loop).detach();
    }

    /* 5. Initialize Network Hub (Windows/Android Gateway) */
    network_init();
    std::thread(network_loop).detach();

    /* 6. Main Loop */
    printf("Mimobot Pro Started!\n");
    while(1) {
        /* Periodically call the lv_task_handler() to handle UI tasks */
        {
            std::lock_guard<std::mutex> lock(lvgl_mutex);
            lv_timer_handler();
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    return 0;
}
