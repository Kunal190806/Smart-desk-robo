package com.kunal.mimobot.util

import android.util.Log
import okhttp3.*
import java.util.concurrent.TimeUnit

object WebSocketManager {
    private const val TAG = "WebSocketManager"
    private var client: OkHttpClient = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()
    
    private var webSocket: WebSocket? = null
    private var currentIp: String = "192.168.1.100"
    private var isForwardingEnabled: Boolean = true
    
    var onStatusChange: ((Boolean) -> Unit)? = null
    var isConnected: Boolean = false
        private set

    fun updateIp(ip: String) {
        if (currentIp != ip) {
            currentIp = ip
            disconnect()
            connect()
        }
    }

    fun setForwardingEnabled(enabled: Boolean) {
        isForwardingEnabled = enabled
    }

    fun connect() {
        val request = Request.Builder()
            .url("ws://$currentIp:8000")
            .build()
        
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket Connected")
                isConnected = true
                onStatusChange?.invoke(true)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d(TAG, "Receiving: $text")
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket Closing: $reason")
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket Closed: $reason")
                isConnected = false
                onStatusChange?.invoke(false)
                reconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket Failure: ${t.message}")
                isConnected = false
                onStatusChange?.invoke(false)
                reconnect()
            }
        })
    }

    private fun reconnect() {
        Thread {
            try {
                Thread.sleep(5000)
                if (!isConnected) {
                    Log.d(TAG, "Attempting to reconnect...")
                    connect()
                }
            } catch (e: InterruptedException) {
                e.printStackTrace()
            }
        }.start()
    }

    fun disconnect() {
        webSocket?.close(1000, "User initiated disconnect")
        webSocket = null
        isConnected = false
    }

    fun sendData(json: String) {
        if (isConnected && isForwardingEnabled) {
            webSocket?.send(json)
            Log.d(TAG, "Sent: $json")
        }
    }
}
