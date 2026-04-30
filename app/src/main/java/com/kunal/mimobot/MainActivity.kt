package com.kunal.mimobot

import android.Manifest
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.work.*
import com.kunal.mimobot.service.CalendarSyncWorker
import com.kunal.mimobot.util.WebSocketManager
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.TimeUnit

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Ensure notification listener is enabled
        if (!isNotificationServiceEnabled()) {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        }

        setContent {
            MimobotTheme {
                DashboardScreen()
            }
        }
        
        setupWorkManager()
    }

    private fun isNotificationServiceEnabled(): Boolean {
        val cn = android.content.ComponentName(this, com.kunal.mimobot.service.MimoNotificationService::class.java)
        val flat = Settings.Secure.getString(contentResolver, "enabled_notification_listeners")
        return flat != null && flat.contains(cn.flattenToString())
    }

    private fun setupWorkManager() {
        val syncRequest = PeriodicWorkRequestBuilder<CalendarSyncWorker>(30, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()

        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "CalendarSync",
            ExistingPeriodicWorkPolicy.KEEP,
            syncRequest
        )
    }
}

@Composable
fun DashboardScreen() {
    val context = LocalContext.current
    var ipAddress by remember { mutableStateOf("192.168.1.100") }
    var isConnected by remember { mutableStateOf(WebSocketManager.isConnected) }
    var isForwarding by remember { mutableStateOf(true) }
    var lastSyncTime by remember { mutableStateOf("Never") }
    
    val notificationLog = remember { mutableStateListOf<NotificationItem>() }

    // Permission handling
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            CalendarSyncWorker.syncCalendar(context)
        }
    }

    LaunchedEffect(Unit) {
        WebSocketManager.onStatusChange = { connected ->
            isConnected = connected
        }
        permissionLauncher.launch(Manifest.permission.READ_CALENDAR)
        
        // Load last sync time from prefs
        val prefs = context.getSharedPreferences("mimobot_prefs", Context.MODE_PRIVATE)
        val lastSync = prefs.getLong("last_calendar_sync", 0)
        if (lastSync > 0) {
            lastSyncTime = SimpleDateFormat("hh:mm a", Locale.getDefault()).format(Date(lastSync))
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF0A0A0A))
            .padding(16.dp)
    ) {
        Text(
            text = "Mimobot",
            color = Color(0xFF00A3FF),
            fontSize = 32.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 24.dp)
        )

        // Connection Status Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A))
        ) {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .background(if (isConnected) Color.Green else Color.Red, RoundedCornerShape(6.dp))
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = if (isConnected) "Connected to $ipAddress" else "Disconnected",
                    color = Color.White,
                    fontSize = 18.sp
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Calendar Sync Section
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A))
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Pairing", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(12.dp))
                Button(
                    onClick = { 
                        context.startActivity(Intent(context, com.kunal.mimobot.ui.PairingActivity::class.java))
                    },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00A3FF))
                ) {
                    Text("Pair via QR Code")
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Calendar Sync Section
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A))
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Calendar Sync Status", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
                Text("Last Synced: $lastSyncTime", color = Color.Gray, fontSize = 14.sp)
                Spacer(modifier = Modifier.height(12.dp))
                Button(
                    onClick = { 
                        CalendarSyncWorker.syncCalendar(context)
                        val now = System.currentTimeMillis()
                        lastSyncTime = SimpleDateFormat("hh:mm a", Locale.getDefault()).format(Date(now))
                    },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00A3FF))
                ) {
                    Text("Sync Now")
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // IP Input
        OutlinedTextField(
            value = ipAddress,
            onValueChange = { 
                ipAddress = it
                WebSocketManager.updateIp(it)
            },
            label = { Text("Pi IP Address", color = Color.Gray) },
            modifier = Modifier.fillMaxWidth(),
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = Color.White,
                unfocusedTextColor = Color.White,
                focusedBorderColor = Color(0xFF00A3FF),
                unfocusedBorderColor = Color.Gray
            )
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Toggle
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("Forward Notifications", color = Color.White, fontSize = 18.sp)
            Switch(
                checked = isForwarding,
                onCheckedChange = { 
                    isForwarding = it
                    WebSocketManager.setForwardingEnabled(it)
                },
                colors = SwitchDefaults.colors(checkedThumbColor = Color(0xFF00A3FF))
            )
        }

        Spacer(modifier = Modifier.height(24.dp))

        Text("Live Notification Log", color = Color.Gray, fontSize = 14.sp)
        
        Spacer(modifier = Modifier.height(8.dp))

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFF141414), RoundedCornerShape(8.dp))
                .padding(8.dp)
        ) {
            items(notificationLog.reversed()) { item ->
                NotificationRow(item)
                HorizontalDivider(color = Color(0xFF222222))
            }
        }
    }
}

@Composable
fun NotificationRow(item: NotificationItem) {
    Column(modifier = Modifier.padding(vertical = 8.dp)) {
        Text(text = item.app, color = Color(0xFF00A3FF), fontSize = 12.sp)
        Text(text = item.title, color = Color.White, fontWeight = FontWeight.Bold)
        Text(text = item.msg, color = Color.LightGray, fontSize = 14.sp)
    }
}

data class NotificationItem(val app: String, val title: String, val msg: String)

@Composable
fun MimobotTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Color(0xFF00A3FF),
            background = Color(0xFF0A0A0A),
            surface = Color(0xFF1A1A1A)
        ),
        content = content
    )
}

@androidx.compose.ui.tooling.preview.Preview
@Composable
fun DashboardPreview() {
    MimobotTheme {
        DashboardScreen()
    }
}
