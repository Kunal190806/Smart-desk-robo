package com.kunal.mimobot.service

import android.content.Context
import android.util.Log
import androidx.work.Worker
import androidx.work.WorkerParameters
import com.kunal.mimobot.util.CalendarManager
import com.kunal.mimobot.util.WebSocketManager
import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar

class CalendarSyncWorker(context: Context, workerParams: WorkerParameters) : Worker(context, workerParams) {
    override fun doWork(): Result {
        Log.d("CalendarSyncWorker", "Starting periodic calendar sync")
        syncCalendar(applicationContext)
        return Result.success()
    }

    companion object {
        fun syncCalendar(context: Context) {
            val events = CalendarManager.getEventsForNext24Hours(context)
            
            // 1. Regular Sync Packet
            val json = JSONObject().apply {
                put("type", "REMINDER")
                put("count", events.size)
                val eventArray = JSONArray()
                events.forEach { event ->
                    eventArray.put(JSONObject().apply {
                        put("title", event.title)
                        put("time", event.time)
                        put("loc", event.loc)
                    })
                }
                put("events", eventArray)
            }
            
            WebSocketManager.sendData(json.toString())

            // 2. Check for 15-minute reminders
            val now = System.currentTimeMillis()
            val fifteenMinsFromNow = now + (15 * 60 * 1000)
            
            events.forEach { event ->
                // If event starts in the next 15-20 minutes (to avoid missing window between syncs)
                if (event.startTimeMillis in fifteenMinsFromNow..(fifteenMinsFromNow + (5 * 60 * 1000))) {
                    val notifJson = JSONObject().apply {
                        put("type", "NOTIF")
                        put("app", "Calendar")
                        put("title", "Upcoming: ${event.title}")
                        put("msg", "Starting at ${event.time}")
                    }
                    WebSocketManager.sendData(notifJson.toString())
                }
            }
            
            // Save last sync time
            val prefs = context.getSharedPreferences("mimobot_prefs", Context.MODE_PRIVATE)
            prefs.edit().putLong("last_calendar_sync", now).apply()
        }
    }
}
