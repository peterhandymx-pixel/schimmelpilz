package de.schimmelpilz.app.ui.screens

import android.app.Activity
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

class PickedFile(val name: String, val mime: String, val bytes: ByteArray)

class DocumentActions(val scan: () -> Unit, val pick: () -> Unit)

/** The server accepts these types; 10 MB per file. */
private val ACCEPTED = arrayOf(
    "application/pdf", "image/png", "image/jpeg", "application/zip",
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
const val MAX_BYTES = 10 * 1024 * 1024

/**
 * Scanning uses Google's on-device document scanner (edge detection, cropping, several pages -> one PDF).
 * The camera runs inside Google Play services, so the app needs no camera permission.
 */
@Composable
fun rememberDocumentActions(onFile: (PickedFile) -> Unit, onError: (String) -> Unit): DocumentActions {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    fun deliver(uri: Uri, name: String, mime: String) = scope.launch {
        val bytes = withContext(Dispatchers.IO) { context.contentResolver.openInputStream(uri)?.use { it.readBytes() } }
        when {
            bytes == null -> onError("read")
            bytes.size > MAX_BYTES -> onError("too_large")
            else -> onFile(PickedFile(name, mime, bytes))
        }
    }
    val scanner = rememberLauncherForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
        if (result.resultCode != Activity.RESULT_OK) return@rememberLauncherForActivityResult
        val pdf = GmsDocumentScanningResult.fromActivityResultIntent(result.data)?.pdf ?: return@rememberLauncherForActivityResult
        val stamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd_HHmm"))
        deliver(pdf.uri, "Scan_$stamp.pdf", "application/pdf")
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) deliver(uri, displayName(context, uri), context.contentResolver.getType(uri) ?: "application/octet-stream")
    }
    return DocumentActions(
        scan = {
            val options = GmsDocumentScannerOptions.Builder()
                .setGalleryImportAllowed(true)
                .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_PDF)
                .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_FULL)
                .build()
            val activity = context as? ComponentActivity
            if (activity == null) onError("scanner") else GmsDocumentScanning.getClient(options).getStartScanIntent(activity)
                .addOnSuccessListener { scanner.launch(IntentSenderRequest.Builder(it).build()) }
                .addOnFailureListener { onError("scanner") }
        },
        pick = { picker.launch(ACCEPTED) },
    )
}

private fun displayName(context: Context, uri: Uri): String =
    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) cursor.getString(0) else null
    } ?: "Dokument"
