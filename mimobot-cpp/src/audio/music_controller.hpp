#ifndef MUSIC_CONTROLLER_HPP
#define MUSIC_CONTROLLER_HPP

// #include <mpd/client.h>
#include <string>

/* Initialize connection to MPD */
bool music_init();

/* Send commands to the player */
void music_play_pause();
void music_next();
void music_prev();

/* Background thread to update song metadata */
void music_update_loop();

#endif // MUSIC_CONTROLLER_HPP
