package com.kunal.mimobot.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import com.kunal.mimobot.util.WebSocketManager
import org.json.JSONObject
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class PairingActivity : ComponentActivity() {
    private lateinit var cameraExecutor: ExecutorService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cameraExecutor = Executors.newSingleThreadExecutor()

        setContent {
            PairingScreen(onQrScanned = { ip ->
                saveIpAndHandshake(ip)
            })
        }
    }

    private fun saveIpAndHandshake(ip: String) {
        val prefs = getSharedPreferences("mimobot_prefs", Context.MODE_PRIVATE)
        prefs.edit().putString("target_pi_ip", ip).apply()
        
        WebSocketManager.updateIp(ip)
        
        val successPacket = JSONObject().apply {
            put("type", "PAIR_SUCCESS")
            put("dev", "Android Phone")
        }
        WebSocketManager.sendData(successPacket.toString())
        
        runOnUiThread {
            Toast.makeText(this, "Mimobot Paired Successfully!", Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
    }
}

@Composable
fun PairingScreen(onQrScanned: (String) -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val cameraProviderFuture = remember { ProcessCameraProvider.getInstance(context) }
    
    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.CAMERA
            ) == PackageManager.PERMISSION_GRANTED
        )
    }

    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { granted: Boolean ->
            hasCameraPermission = granted
        }
    )

    LaunchedEffect(key1 = true) {
        if (!hasCameraPermission) {
            launcher.launch(Manifest.permission.CAMERA)
        }
    }

    if (hasCameraPermission) {
        Box(modifier = Modifier.fillMaxSize()) {
            AndroidView(
                factory = { ctx ->
                    val previewView = PreviewView(ctx)
                    val executor = ContextCompat.getMainExecutor(ctx)
                    cameraProviderFuture.addListener({
                        val cameraProvider = cameraProviderFuture.get()
                        val preview = Preview.Builder().build().also {
                            it.setSurfaceProvider(previewView.surfaceProvider)
                        }

                        val scanner = BarcodeScanning.getClient()
                        val imageAnalysis = ImageAnalysis.Builder()
                            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                            .build()

                        imageAnalysis.setAnalyzer(executor) { imageProxy ->
                            processImageProxy(scanner, imageProxy, onQrScanned)
                        }

                        val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

                        try {
                            cameraProvider.unbindAll()
                            cameraProvider.bindToLifecycle(
                                lifecycleOwner,
                                cameraSelector,
                                preview,
                                imageAnalysis
                            )
                        } catch (e: Exception) {
                            Log.e("PairingActivity", "Use case binding failed", e)
                        }
                    }, executor)
                    previewView
                },
                modifier = Modifier.fillMaxSize()
            )

            Canvas(modifier = Modifier.fillMaxSize()) {
                val squareSize = 250.dp.toPx()
                val left = (size.width - squareSize) / 2
                val top = (size.height - squareSize) / 2
                drawRoundRect(
                    color = Color.White,
                    topLeft = Offset(left, top),
                    size = Size(squareSize, squareSize),
                    style = Stroke(width = 4.dp.toPx()),
                    cornerRadius = CornerRadius(12.dp.toPx())
                )
            }
        }
    }
}

@androidx.annotation.OptIn(androidx.camera.core.ExperimentalGetImage::class)
private fun processImageProxy(
    scanner: com.google.mlkit.vision.barcode.BarcodeScanner,
    imageProxy: ImageProxy,
    onQrScanned: (String) -> Unit
) {
    val mediaImage = imageProxy.image
    if (mediaImage != null) {
        val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
        scanner.process(image)
            .addOnSuccessListener { barcodes ->
                for (barcode in barcodes) {
                    barcode.rawValue?.let { value ->
                        if (value.matches(Regex("""^(\d{1,3}\.){3}\d{1,3}$"""))) {
                            onQrScanned(value)
                            scanner.close()
                        }
                    }
                }
            }
            .addOnFailureListener {
                Log.e("PairingActivity", "QR detection failed", it)
            }
            .addOnCompleteListener {
                imageProxy.close()
            }
    } else {
        imageProxy.close()
    }
}
