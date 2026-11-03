package de.schimmelpilz.app.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.DocumentScanner
import androidx.compose.material.icons.outlined.UploadFile
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import de.schimmelpilz.app.AppState
import de.schimmelpilz.app.data.ApiException
import de.schimmelpilz.app.data.Dates
import de.schimmelpilz.app.data.InboxItem
import de.schimmelpilz.app.ui.DateField
import de.schimmelpilz.app.ui.LocalLang
import de.schimmelpilz.app.ui.errorText
import de.schimmelpilz.app.ui.rememberFileOpener
import de.schimmelpilz.app.ui.tr
import kotlinx.coroutines.launch

@Composable
fun InboxScreen(state: AppState) {
    val inbox by state.inbox.collectAsStateWithLifecycle()
    val cases by state.cases.collectAsStateWithLifecycle()
    val lang = LocalLang.current
    val scope = rememberCoroutineScope()
    var view by remember { mutableIntStateOf(0) }
    var pending by remember { mutableStateOf<PickedFile?>(null) }
    var assigning by remember { mutableStateOf<InboxItem?>(null) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    val tooLarge = tr("Datei ist größer als 10 MB.", "File is larger than 10 MB.")
    val failed = tr("Das hat nicht geklappt. Bitte erneut versuchen.", "That did not work. Please try again.")
    val files = rememberFileOpener(state.api)
    val docs = rememberDocumentActions(onFile = { pending = it }, onError = { message = if (it == "too_large") tooLarge else failed })
    val open = inbox.filter { it.caseId == null }
    val assigned = inbox.filter { it.caseId != null }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        ScreenTitle(tr("Posteingang", "Inbox"))
        if (busy || files.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Button(onClick = docs.scan, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp), contentPadding = PaddingValues(18.dp)) {
                    Box(Modifier.size(46.dp).clip(RoundedCornerShape(16.dp)).background(MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.14f)), contentAlignment = Alignment.Center) {
                        Icon(Icons.Outlined.DocumentScanner, null)
                    }
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text(tr("Brief scannen", "Scan a letter"), style = MaterialTheme.typography.titleMedium)
                        Text(tr("Seiten fotografieren, als PDF speichern", "Photograph pages, save as PDF"), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            item {
                FilledTonalButton(onClick = docs.pick, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp)) {
                    Icon(Icons.Outlined.UploadFile, null); Spacer(Modifier.width(8.dp)); Text(tr("Datei hochladen", "Upload a file"))
                }
            }
            message?.let { item { Text(it, color = MaterialTheme.colorScheme.primary) } }
            item {
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    SegmentedButton(view == 0, { view = 0 }, SegmentedButtonDefaults.itemShape(0, 2)) { Text(tr("Ohne Zuordnung · ", "Unassigned · ") + open.size) }
                    SegmentedButton(view == 1, { view = 1 }, SegmentedButtonDefaults.itemShape(1, 2)) { Text(tr("Zugeordnet · ", "Assigned · ") + assigned.size) }
                }
            }
            val shown = if (view == 0) open else assigned
            if (shown.isEmpty()) item { Text(if (view == 0) tr("Keine offenen Eingänge.", "No unassigned items.") else tr("Noch nichts zugeordnet.", "Nothing assigned yet."), color = MaterialTheme.colorScheme.onSurfaceVariant) }
            items(shown, key = { it.id }) { item -> InboxCard(item, lang, onOpen = { files.open("api/inbox/${item.id}/download", item.name, false) }, onAssign = { assigning = item }) }
            item {
                Text(tr("Zuordnung nur auf Ihre Bestätigung. Originaldateien bleiben unverändert erhalten.", "Assignment only on your confirmation. Original files are kept unchanged."),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 16.dp))
            }
        }
    }

    pending?.let { file ->
        UploadDialog(file, onDismiss = { pending = null }, onSave = { received, subject, sender ->
            busy = true; message = null
            scope.launch {
                try { state.api.upload(file.name, file.mime, file.bytes, received, subject, sender); state.refresh().join(); pending = null; view = 0 }
                catch (e: ApiException) { message = failed + if (e.detail.isNotBlank()) " (${e.detail})" else "" }
                finally { busy = false }
            }
        })
    }
    assigning?.let { item ->
        var choice by remember(item) { mutableStateOf<String?>(null) }
        var error by remember(item) { mutableStateOf<String?>(null) }
        AlertDialog(
            onDismissRequest = { assigning = null },
            title = { Text(tr("Welcher Akte zuordnen?", "Assign to which case?")) },
            text = {
                Column {
                    cases.forEach { c ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(choice == c.id, { choice = c.id })
                            Text("${c.reference} · ${c.title}", maxLines = 2, overflow = TextOverflow.Ellipsis)
                        }
                    }
                    error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            },
            confirmButton = {
                TextButton(enabled = choice != null && !busy, onClick = {
                    busy = true
                    scope.launch {
                        try { state.api.assign(item, choice!!); state.refresh().join(); assigning = null }
                        catch (e: ApiException) { error = failed }
                        finally { busy = false }
                    }
                }) { Text(tr("Zuordnen", "Assign")) }
            },
            dismissButton = { TextButton(onClick = { assigning = null }) { Text(tr("Abbrechen", "Cancel")) } },
        )
    }
}

@Composable
private fun InboxCard(item: InboxItem, lang: String, onOpen: () -> Unit, onAssign: () -> Unit) {
    Surface(onClick = onOpen, shape = RoundedCornerShape(22.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row {
                Box(Modifier.size(width = 44.dp, height = 54.dp).clip(RoundedCornerShape(8.dp)).background(MaterialTheme.colorScheme.errorContainer), contentAlignment = Alignment.Center) {
                    Text(item.name.substringAfterLast('.', "").uppercase().take(4), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onErrorContainer)
                }
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(item.subject.ifBlank { item.name }, style = MaterialTheme.typography.titleMedium)
                    if (item.sender.isNotBlank()) Text(item.sender, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(tr("Eingang ", "Received ") + Dates.label(item.receivedOn, lang) + " · " + item.name, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    item.caseReference?.let { Text(tr("Akte ", "Case ") + it + (item.caseTitle?.let { t -> " · $t" } ?: ""), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary) }
                }
            }
            if (item.caseId == null) OutlinedButton(onClick = onAssign, modifier = Modifier.fillMaxWidth()) { Text(tr("Akte zuordnen …", "Assign to case …")) }
        }
    }
}

@Composable
private fun UploadDialog(file: PickedFile, onDismiss: () -> Unit, onSave: (received: String, subject: String, sender: String) -> Unit) {
    var received by remember { mutableStateOf(Dates.today().toString()) }
    var subject by remember { mutableStateOf("") }
    var sender by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(tr("In den Posteingang", "Add to inbox")) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(file.name + " · " + (file.bytes.size / 1024).coerceAtLeast(1) + " KB", style = MaterialTheme.typography.bodyMedium)
                DateField(received, { received = it }, tr("Eingangsdatum", "Received on"), Modifier.fillMaxWidth())
                OutlinedTextField(subject, { subject = it }, label = { Text(tr("Betreff (optional)", "Subject (optional)")) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(sender, { sender = it }, label = { Text(tr("Absender (optional)", "Sender (optional)")) }, singleLine = true, modifier = Modifier.fillMaxWidth())
            }
        },
        confirmButton = { TextButton(enabled = received.isNotBlank(), onClick = { onSave(received, subject.trim(), sender.trim()) }) { Text(tr("Speichern", "Save")) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(tr("Abbrechen", "Cancel")) } },
    )
}
