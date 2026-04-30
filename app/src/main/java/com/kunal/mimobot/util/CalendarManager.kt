package com.kunal.mimobot.util

import android.content.ContentUris
import android.content.Context
import android.database.Cursor
import android.net.Uri
import android.provider.CalendarContract
import java.text.SimpleDateFormat
import java.util.*

data class CalendarEvent(
    val title: String,
    val time: String,
    val loc: String,
    val startTimeMillis: Long
)

object CalendarManager {
    fun getEventsForNext24Hours(context: Context): List<CalendarEvent> {
        val events = mutableListOf<CalendarEvent>()
        val contentResolver = context.contentResolver
        
        val beginTime = Calendar.getInstance()
        val endTime = Calendar.getInstance().apply {
            add(Calendar.HOUR_OF_DAY, 24)
        }

        val builder: Uri.Builder = CalendarContract.Instances.CONTENT_URI.buildUpon()
        ContentUris.appendId(builder, beginTime.timeInMillis)
        ContentUris.appendId(builder, endTime.timeInMillis)

        val projection = arrayOf(
            CalendarContract.Instances.TITLE,
            CalendarContract.Instances.BEGIN,
            CalendarContract.Instances.EVENT_LOCATION,
            CalendarContract.Instances.SELF_ATTENDEE_STATUS
        )

        val cursor: Cursor? = contentResolver.query(
            builder.build(),
            projection,
            null,
            null,
            CalendarContract.Instances.BEGIN + " ASC"
        )

        val timeFormat = SimpleDateFormat("HH:mm", Locale.getDefault())

        cursor?.use {
            while (it.moveToNext()) {
                val title = it.getString(0) ?: "No Title"
                val startTime = it.getLong(1)
                val location = it.getString(2) ?: ""
                val status = it.getInt(3)

                // Filter for Accepted (1) or Tentative (4)
                if (status == CalendarContract.Attendees.ATTENDEE_STATUS_ACCEPTED ||
                    status == CalendarContract.Attendees.ATTENDEE_STATUS_TENTATIVE ||
                    status == CalendarContract.Attendees.ATTENDEE_STATUS_NONE // Fallback for own events
                ) {
                    events.add(
                        CalendarEvent(
                            title = title,
                            time = timeFormat.format(Date(startTime)),
                            loc = location,
                            startTimeMillis = startTime
                        )
                    )
                }
            }
        }
        return events
    }
}
