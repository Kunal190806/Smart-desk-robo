#ifndef NETWORK_MANAGER_HPP
#define NETWORK_MANAGER_HPP

#include <string>

/* Initialize the WebSocket server on port 8000 */
void network_init();

/* Main loop for network events (call in a separate thread) */
void network_loop();

/* Send a message to all connected clients (Windows/Android) */
void network_broadcast(const std::string& message);

#endif // NETWORK_MANAGER_HPP
