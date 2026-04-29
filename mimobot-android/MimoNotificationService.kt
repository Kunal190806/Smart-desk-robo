package com.kunal.mimobot

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class MimoNotificationService : NotificationListenerService() {

    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .build()

    // ─── Spam filter: ignore these system/silent apps ───────────────────────
    private val ignoredPackages = setOf(
        "android", "com.android.systemui", "com.android.phone",
        "com.google.android.gms", "com.android.providers.downloads",
        "com.google.android.googlequicksearchbox"
    )

    // ─── App display name map ────────────────────────────────────────────────
    private val appNames = mapOf(
        "com.discord" to "Discord",
        "com.whatsapp" to "WhatsApp",
        "com.instagram.android" to "Instagram",
        "com.google.android.apps.messaging" to "Messages",
        "com.snapchat.android" to "Snapchat",
        "com.twitter.android" to "Twitter/X",
        "org.telegram.messenger" to "Telegram",
        "com.spotify.music" to "Spotify",
        "com.google.android.youtube" to "YouTube",
        "com.microsoft.teams" to "Teams",
        "com.slack" to "Slack",
        "com.gmail" to "Gmail",
        "com.google.android.gm" to "Gmail"
    )

    // ─── Comprehensive emoji → text shortcode map ────────────────────────────
    private val emojiMap = mapOf(
        "😀" to ":grin:", "😂" to ":joy:", "🤣" to ":rofl:", "😊" to ":blush:",
        "😍" to ":heart_eyes:", "🥰" to ":smiling_face:", "😘" to ":kiss:",
        "😭" to ":sob:", "😢" to ":cry:", "😡" to ":rage:", "🤬" to ":angry:",
        "😱" to ":scream:", "😴" to ":sleeping:", "🤔" to ":thinking:",
        "🙄" to ":eye_roll:", "😏" to ":smirk:", "😎" to ":sunglasses:",
        "🤯" to ":mind_blown:", "😤" to ":triumph:", "🥳" to ":party:",
        "🤩" to ":star_struck:", "😬" to ":grimace:", "🤫" to ":shushing:",
        "🤗" to ":hug:", "🫡" to ":salute:", "🫠" to ":melting:",
        "❤️" to ":heart:", "🧡" to ":orange_heart:", "💛" to ":yellow_heart:",
        "💚" to ":green_heart:", "💙" to ":blue_heart:", "💜" to ":purple_heart:",
        "🖤" to ":black_heart:", "🤍" to ":white_heart:", "💔" to ":broken_heart:",
        "❤‍🔥" to ":heart_fire:", "💕" to ":two_hearts:", "💞" to ":revolving_hearts:",
        "💯" to ":100:", "🔥" to ":fire:", "✨" to ":sparkles:", "⭐" to ":star:",
        "🌟" to ":glowing_star:", "💫" to ":dizzy:", "💥" to ":boom:",
        "🎉" to ":tada:", "🎊" to ":confetti:", "🥂" to ":clinking_glasses:",
        "👍" to ":thumbsup:", "👎" to ":thumbsdown:", "👏" to ":clap:",
        "🙏" to ":folded_hands:", "🤝" to ":handshake:", "👋" to ":wave:",
        "✌️" to ":peace:", "🤞" to ":fingers_crossed:", "🫶" to ":heart_hands:",
        "💪" to ":muscle:", "🫂" to ":people_hugging:", "👀" to ":eyes:",
        "😂💀" to ":dead:", "💀" to ":skull:", "👻" to ":ghost:",
        "🚀" to ":rocket:", "🎮" to ":game:", "📱" to ":phone:",
        "💻" to ":laptop:", "🎵" to ":music:", "🎶" to ":musical_notes:",
        "📸" to ":camera:", "🍕" to ":pizza:", "☕" to ":coffee:",
        "🍺" to ":beer:", "🏠" to ":house:", "✅" to ":check:", "❌" to ":x:",
        "⚠️" to ":warning:", "🔔" to ":bell:", "📢" to ":announcement:",
        "🔗" to ":link:", "📎" to ":paperclip:", "🗑️" to ":trash:",
        "📝" to ":memo:", "📅" to ":calendar:", "⏰" to ":alarm:",
        "🔑" to ":key:", "🔒" to ":lock:", "💸" to ":money:", "💰" to ":moneybag:"
    )

    override fun onCreate() {
        super.onCreate()
        connectToMimobot()
    }

    private fun connectToMimobot() {
        val request = Request.Builder().url("ws://192.168.1.100:8000").build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("Mimobot", "Phone Connected to Hub!")
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("Mimobot", "Connection Failed: ${t.message}")
                // Retry after 5 seconds
                android.os.Handler(mainLooper).postDelayed({ connectToMimobot() }, 5000)
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                android.os.Handler(mainLooper).postDelayed({ connectToMimobot() }, 5000)
            }
        })
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val packageName = sbn.packageName

        // ── Filter out spam ──────────────────────────────────────────────────
        if (packageName in ignoredPackages) return
        if (sbn.notification.flags and android.app.Notification.FLAG_FOREGROUND_SERVICE != 0) return
        if (sbn.isOngoing) return // skip media/persistent notifications

        val extras = sbn.notification.extras
        val rawTitle = extras.getString("android.title") ?: return  // no title = ignore
        val rawText  = extras.getCharSequence("android.text")?.toString() ?: ""

        // ── Sanitize both fields ─────────────────────────────────────────────
        val title   = sanitize(rawTitle)
        val text    = sanitize(rawText)
        val appName = appNames[packageName] ?: packageName.substringAfterLast(".")
            .replaceFirstChar { it.uppercase() }

        // ── Build clean JSON using JSONObject (safe escaping) ────────────────
        val json = JSONObject().apply {
            put("type",  "NOTIF")
            put("app",   appName)
            put("title", title)
            put("msg",   text)
        }.toString()

        webSocket?.send(json)
        Log.d("Mimobot", "Notif -> $appName | $title | $text")
    }

    // ─── Text Sanitization Engine ────────────────────────────────────────────
    private fun sanitize(input: String): String {
        var text = input

        // 1. Replace known emojis with readable shortcodes (longest match first)
        //    Sort by length descending so multi-char emojis match before sub-chars
        for ((emoji, code) in emojiMap.entries.sortedByDescending { it.key.length }) {
            text = text.replace(emoji, " $code ")
        }

        // 2. Strip any remaining emoji / symbol Unicode blocks that LVGL can't render.
        //    Keep: Basic Latin, Latin Extended, Devanagari (Hindi), common CJK, Arabic, Cyrillic
        text = text.replace(Regex(
            "[\\uFE00-\\uFE0F]|"        +  // variation selectors
            "[\\u200B-\\u200F]|"        +  // zero-width chars
            "[\\u2028\\u2029]|"         +  // line/paragraph separators
            "[\\uD83C-\\uDBFF][\\uDC00-\\uDFFF]|" + // surrogate pairs (most color emoji)
            "[\\u2600-\\u27BF]"         +  // misc symbols & dingbats (unhandled ones)
            "|[\\u{1F000}-\\u{1FFFF}]"     // everything in supplementary planes
        ), "")

        // 3. Normalize whitespace (multiple spaces → single space)
        text = text.replace(Regex("\\s+"), " ").trim()

        // 4. Truncate to 120 chars so the Pi screen doesn't overflow
        if (text.length > 120) text = text.take(117) + "..."

        return text
    }
}
