#include "music_controller.hpp"
#include "ui/ui_manager.hpp"
#include <thread>
#include <chrono>

static struct mpd_connection *conn = NULL;

bool music_init() {
    conn = mpd_connection_new("127.0.0.1", 6600, 30000);
    if (mpd_connection_get_error(conn) != MPD_ERROR_SUCCESS) {
        printf("MPD Connection Failed: %s\n", mpd_connection_get_error_message(conn));
        return false;
    }
    return true;
}

void music_play_pause() {
    if(!conn) return;
    struct mpd_status * status = mpd_run_status(conn);
    if(status) {
        if(mpd_status_get_state(status) == MPD_STATE_PLAY) mpd_run_pause(conn, true);
        else mpd_run_play(conn);
        mpd_status_free(status);
    }
}

void music_next() {
    if(conn) mpd_run_next(conn);
}

void music_prev() {
    if(conn) mpd_run_previous(conn);
}

void music_update_loop() {
    while(true) {
        if(!conn) {
            std::this_thread::sleep_for(std::chrono::seconds(2));
            music_init();
            continue;
        }

        struct mpd_song *song = mpd_run_current_song(conn);
        if (song != NULL) {
            const char *title = mpd_song_get_tag(song, MPD_TAG_TITLE, 0);
            const char *artist = mpd_song_get_tag(song, MPD_TAG_ARTIST, 0);
            
            ui_update_song(title ? title : "Unknown Title", 
                           artist ? artist : "Unknown Artist");
            
            mpd_song_free(song);
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    }
}
