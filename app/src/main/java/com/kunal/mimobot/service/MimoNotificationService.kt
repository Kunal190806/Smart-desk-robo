package com.kunal.mimobot.service

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.kunal.mimobot.util.WebSocketManager
import org.json.JSONObject
import android.media.MediaMetadata
import android.media.session.MediaSessionManager
import android.content.Context
import android.content.ComponentName

class MimoNotificationService : NotificationListenerService() {
    private val TAG = "MimoNotifService"

    override fun onListenerConnected() {
        super.onListenerConnected()
        Log.d(TAG, "Notification Listener Connected")
        WebSocketManager.connect()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        val sbnNonNull = sbn ?: return
        
        val packageName = sbnNonNull.packageName
        
        // Filter spam
        if (packageName == "android.process.acore" || packageName == "android") return
        
        val extras = sbnNonNull.notification.extras
        val title = extras.getString("android.title") ?: ""
        val text = extras.getCharSequence("android.text")?.toString() ?: ""
        
        if (title.isBlank() && text.isBlank()) return

        val json = JSONObject().apply {
            put("type", "NOTIF")
            put("app", packageName)
            put("title", title)
            put("msg", text)
        }
        
        WebSocketManager.sendData(json.toString())
        
        // Detect Discord Voice via Notification
        if (packageName == "com.discord") {
            if (text.contains("Connected to") || title.contains("Voice")) {
                val discordJson = JSONObject().apply {
                    put("type", "DISCORD_ACTIVE")
                    put("channel", text)
                }
                WebSocketManager.sendData(discordJson.toString())
            }
        }
        
        // Detect Media
        checkMediaSession()
    }

    private fun checkMediaSession() {
        val manager = getSystemService(Context.MEDIA_SESSION_SERVICE) as MediaSessionManager
        val component = ComponentName(this, this::class.java)
        val controllers = manager.getActiveSessions(component)
        
        for (controller in controllers) {
            val metadata = controller.metadata
            if (metadata != null) {
                val track = metadata.getString(MediaMetadata.METADATA_KEY_TITLE) ?: "Unknown"
                val artist = metadata.getString(MediaMetadata.METADATA_KEY_ARTIST) ?: "Unknown"
                
                val mediaJson = JSONObject().apply {
                    put("type", "MEDIA_ACTIVE")
                    put("track", track)
                    put("artist", artist)
                }
                WebSocketManager.sendData(mediaJson.toString())
            }
        }
    }
}
