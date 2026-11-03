package de.schimmelpilz.app.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.webkit.MimeTypeMap
import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.FileProvider
import de.schimmelpilz.app.data.Api
import de.schimmelpilz.app.data.ApiException
import kotlinx.coroutines.launch
import java.io.File

/** Opens server files (originals, drafts, inbox mail) in a viewer app on the phone, or hands them to the share sheet. */
class FileOpener(val busy: Boolean, val open: (path: String, name: String, share: Boolean) -> Unit)

@Composable
fun rememberFileOpener(api: Api): FileOpener {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    val failed = tr("Datei konnte nicht geladen werden.", "Could not load the file.")
    val noViewer = tr("Keine App zum Öffnen dieser Datei gefunden.", "No app found to open this file.")
    return FileOpener(busy) { path, name, share ->
        if (!busy) {
            busy = true
            scope.launch {
                try {
                    val file = api.download(path, File(context.cacheDir, "exports/" + safeName(name)))
                    launch(context, file, share)
                } catch (e: ApiException) {
                    Toast.makeText(context, failed, Toast.LENGTH_LONG).show()
                } catch (e: ActivityNotFoundException) {
                    Toast.makeText(context, noViewer, Toast.LENGTH_LONG).show()
                } finally { busy = false }
            }
        }
    }
}

/** Keeps the cache path inside exports/: no separators or control characters from server-side names. */
fun safeName(name: String): String =
    name.replace(Regex("[^\\p{L}\\p{N} ._()-]"), "_").trim('.', ' ').take(120).ifBlank { "Datei" }

fun mimeOf(name: String): String =
    MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase()) ?: "application/octet-stream"

private fun launch(context: Context, file: File, share: Boolean) {
    val uri = FileProvider.getUriForFile(context, context.packageName + ".files", file)
    val mime = mimeOf(file.name)
    val intent = if (share) Intent.createChooser(Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), file.name)
    else Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    context.startActivity(intent)
}
