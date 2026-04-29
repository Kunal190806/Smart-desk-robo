#include "network_manager.hpp"
#include "ui/ui_manager.hpp"
#include <stdio.h>
#include <thread>

/* 
 * This is a simplified wrapper. When you build this on the Pi, 
 * we will link the mongoose.c library to handle the actual WebSocket protocol.
 */

void handle_incoming_message(const std::string& msg) {
    printf("Network: Received message -> %s\n", msg.c_str());
    
    // Example logic for the hub:
    if (msg.find("\"type\":\"NOTIF\"") != std::string::npos) {
        // Parse: {"type":"NOTIF", "app":"WhatsApp", "title":"Kunal", "msg":"hey!"}
        char app[64]  = {0};
        char title[128] = {0};
        char body[256]  = {0};

        // Extract "app" field
        auto appPos = msg.find("\"app\":\"");
        if(appPos != std::string::npos) {
            appPos += 7;
            auto end = msg.find("\"", appPos);
            if(end != std::string::npos)
                strncpy(app, msg.c_str() + appPos, std::min((int)(end - appPos), 63));
        }

        // Extract "title" field
        auto titlePos = msg.find("\"title\":\"");
        if(titlePos != std::string::npos) {
            titlePos += 9;
            auto end = msg.find("\"", titlePos);
            if(end != std::string::npos)
                strncpy(title, msg.c_str() + titlePos, std::min((int)(end - titlePos), 127));
        }

        // Extract "msg" field
        auto msgPos = msg.find("\"msg\":\"");
        if(msgPos != std::string::npos) {
            msgPos += 7;
            auto end = msg.find("\"", msgPos);
            if(end != std::string::npos)
                strncpy(body, msg.c_str() + msgPos, std::min((int)(end - msgPos), 255));
        }

        // Display: "AppName: Title - Body" on Pi
        char display[512] = {0};
        if(strlen(title) > 0 && strlen(body) > 0)
            snprintf(display, sizeof(display), "%s: %s", title, body);
        else if(strlen(title) > 0)
            snprintf(display, sizeof(display), "%s", title);
        else
            snprintf(display, sizeof(display), "%s", body);

        ui_show_notif(strlen(app) ? app : "App", display);
    } else if (msg.find("\"type\":\"ACTION\"") != std::string::npos) {
        printf("Mimobot Hub: Stream Deck action received from Windows!\n");
        // Execute system command or relay back to PC
    } else if (msg.find("\"type\":\"SYNC_ICON\"") != std::string::npos) {
        printf("Mimobot Hub: New App Icon received from Windows!\n");
        ui_update_icon(1, "base64_data"); 
    } else if (msg.find("\"type\":\"TELEMETRY\"") != std::string::npos) {
        // Simplified raw string parsing to avoid heavy JSON libraries in this demo file
        int cpu = 0, gpu = 0, disk = 0;
        char ram[16] = {0};
        
        // Very basic parsing for demo:
        sscanf(msg.c_str(), "%*[^c]cpu\":%d,\"gpu\":%d,\"ram\":\"%15[^\"]\",\"disk\":%d", &cpu, &gpu, ram, &disk);
        ui_update_telemetry(cpu, gpu, ram, disk);
    } else if (msg.find("\"type\":\"MEDIA_ACTIVE\"") != std::string::npos) {
        ui_set_dynamic_mode(true, false);
    } else if (msg.find("\"type\":\"DISCORD_ACTIVE\"") != std::string::npos) {
        ui_set_dynamic_mode(false, true);
    }
}

void network_init() {
    printf("Network Manager: Initializing Server on Port 8000...\n");
    // [Mongoose Server Setup Logic would go here]
}

void network_loop() {
    printf("Network Manager: Thread Started.\n");
    while (true) {
        // [Poll Mongoose Events]
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

void network_broadcast(const std::string& message) {
    printf("Network: Broadcasting to ecosystem -> %s\n", message.c_str());
}
