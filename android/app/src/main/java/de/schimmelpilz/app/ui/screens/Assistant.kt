package de.schimmelpilz.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowUpward
import androidx.compose.material.icons.outlined.ArrowDropDown
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.DocumentScanner
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.UploadFile
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.content.Intent
import android.speech.RecognizerIntent
import android.widget.Toast
import de.schimmelpilz.app.data.ApiException
import de.schimmelpilz.app.data.ResearchRun
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import de.schimmelpilz.app.AppState
import de.schimmelpilz.app.data.CaseFile
import de.schimmelpilz.app.data.Dates
import de.schimmelpilz.app.ui.Avatar
import de.schimmelpilz.app.ui.LocalLang
import de.schimmelpilz.app.ui.theme.LocalBrand
import de.schimmelpilz.app.ui.BrandLockup
import de.schimmelpilz.app.ui.tr

@Composable
fun AssistantScreen(state: AppState, onAsk: (caseId: String, question: String) -> Unit, onOpenChat: (caseId: String) -> Unit, onOpenDeadlines: () -> Unit, onOpenMore: () -> Unit) {
    val user by state.user.collectAsStateWithLifecycle()
    val cases by state.cases.collectAsStateWithLifecycle()
    val lang = LocalLang.current
    var question by remember { mutableStateOf("") }
    // Preselect the case with the nearest upcoming date, else the newest case.
    var caseId by remember(cases) { mutableStateOf((cases.filter { c -> (c.nextDue?.first?.let { Dates.daysUntil(it) } ?: -1) >= 0 }.minByOrNull { it.nextDue!!.first } ?: cases.firstOrNull())?.id) }
    val selected = cases.firstOrNull { it.id == caseId }
    var history by remember { mutableStateOf(false) }
    val attach = rememberCaseUpload(state, selected)
    if (history) HistorySheet(state, cases, onOpen = { history = false; onOpenChat(it) }, onDismiss = { history = false })
    val next = cases.mapNotNull { c -> c.nextDue?.let { Triple(it.first, it.second, c) } }.filter { (Dates.daysUntil(it.first) ?: -1) >= 0 }.minByOrNull { it.first }

    Column(Modifier.fillMaxSize().statusBarsPadding().imePadding()) {
        Row(Modifier.fillMaxWidth().padding(start = 4.dp, end = 20.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { history = true }) { Icon(Icons.Outlined.History, tr("Frühere Fragen", "Earlier questions")) }
            BrandLockup(Modifier.weight(1f), compact = true, scale = 0.82f)
            Avatar(user?.initials ?: "", modifier = Modifier.clip(CircleShape).clickable(onClickLabel = tr("Konto und Einstellungen", "Account and settings"), onClick = onOpenMore))
        }
        Column(Modifier.weight(1f).fillMaxWidth().padding(horizontal = 28.dp), verticalArrangement = Arrangement.Center) {
            Text(
                tr("Hallo, ", "Hello, ") + (user?.firstName ?: ""),
                style = MaterialTheme.typography.displaySmall.merge(TextStyle(brush = LocalBrand.current.greeting)),
            )
            Text(
                if (cases.isEmpty()) tr("Legen Sie zuerst eine Akte an, dann können Sie Fragen dazu stellen.", "Create a case first, then you can ask questions about it.")
                else tr("Woran arbeiten wir heute?", "What are we working on today?"),
                style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Medium, fontSize = 26.sp),
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
            )
            next?.let { (date, title, _) ->
                Spacer(Modifier.height(18.dp))
                Row(
                    Modifier.clip(RoundedCornerShape(50)).background(LocalBrand.current.warning).clickable(onClick = onOpenDeadlines).padding(horizontal = 14.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Outlined.CalendarMonth, null, tint = LocalBrand.current.onWarning, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(tr("Nächste Frist: ", "Next deadline: ") + Dates.label(date, lang) + " · " + title, color = LocalBrand.current.onWarning,
                        style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
        }
        if (selected != null) {
            val suggestions = listOf(
                tr("Fasse die Akte kurz zusammen", "Summarise this case briefly"),
                tr("Welche Fristen sind zu beachten?", "Which deadlines apply?"),
                tr("Welche Unterlagen fehlen noch?", "Which documents are still missing?"),
            )
            LazyRow(Modifier.padding(bottom = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp)) {
                items(suggestions) { text ->
                    Column(
                        Modifier.width(172.dp).heightIn(min = 92.dp).clip(RoundedCornerShape(20.dp)).background(MaterialTheme.colorScheme.surfaceVariant)
                            .clickable { onAsk(selected.id, text) }.padding(14.dp),
                        verticalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(text, style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium))
                        Spacer(Modifier.height(8.dp))
                        Text(selected.reference, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, maxLines = 1, softWrap = false, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
        Composer(
            value = question, onValue = { question = it }, cases = cases, selected = selected, onSelect = { caseId = it }, attach = attach,
            onSend = { selected?.let { onAsk(it.id, question.trim()); question = "" } },
        )
    }
}

@Composable
fun Composer(value: String, onValue: (String) -> Unit, cases: List<CaseFile>, selected: CaseFile?, onSelect: (String) -> Unit, onSend: () -> Unit,
             placeholder: String? = null, attach: DocumentActions? = null) {
    var menu by remember { mutableStateOf(false) }
    var attachMenu by remember { mutableStateOf(false) }
    val context = LocalContext.current
    // Speech input through the phone's own recogniser (Google app); hidden when the phone has none.
    val speech = remember { Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM) }
    val canSpeak = remember { speech.resolveActivity(context.packageManager) != null }
    val lang = LocalLang.current
    val listen = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { spoken -> onValue(listOf(value.trim(), spoken).filter { it.isNotEmpty() }.joinToString(" ")) }
    }
    val speakPrompt = tr("Frage einsprechen", "Speak your question")
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp).clip(RoundedCornerShape(28.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant).padding(start = 8.dp, end = 8.dp, top = 6.dp, bottom = 8.dp),
    ) {
        TextField(
            value, onValue, placeholder = { Text(placeholder ?: tr("Fragen Sie Schimmelpilz", "Ask Schimmelpilz")) },
            colors = TextFieldDefaults.colors(
                focusedContainerColor = Color.Transparent, unfocusedContainerColor = Color.Transparent,
                focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent,
            ),
            maxLines = 6, modifier = Modifier.fillMaxWidth(),
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (attach != null) Box {
                IconButton(onClick = { attachMenu = true }, enabled = selected != null) { Icon(Icons.Outlined.Add, tr("Dokument oder Foto zur Akte hinzufügen", "Add a document or photo to the case")) }
                DropdownMenu(attachMenu, onDismissRequest = { attachMenu = false }) {
                    DropdownMenuItem(text = { Text(tr("Scannen / Foto", "Scan / photo")) }, leadingIcon = { Icon(Icons.Outlined.DocumentScanner, null) }, onClick = { attachMenu = false; attach.scan() })
                    DropdownMenuItem(text = { Text(tr("Datei wählen", "Choose file")) }, leadingIcon = { Icon(Icons.Outlined.UploadFile, null) }, onClick = { attachMenu = false; attach.pick() })
                }
            }
            Box {
                OutlinedButton(onClick = { menu = true }, enabled = cases.isNotEmpty(), contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 12.dp), modifier = Modifier.height(36.dp)) {
                    Icon(Icons.Outlined.Folder, null, Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(selected?.let { tr("Akte: ", "Case: ") + it.reference } ?: tr("Keine Akte", "No case"), style = MaterialTheme.typography.labelLarge)
                    Icon(Icons.Outlined.ArrowDropDown, null, Modifier.size(18.dp))
                }
                DropdownMenu(menu, onDismissRequest = { menu = false }) {
                    cases.forEach { item ->
                        DropdownMenuItem(text = { Text("${item.reference} · ${item.title}", maxLines = 1, overflow = TextOverflow.Ellipsis) }, onClick = { onSelect(item.id); menu = false })
                    }
                }
            }
            Spacer(Modifier.weight(1f))
            if (canSpeak) IconButton(onClick = {
                runCatching { listen.launch(Intent(speech).putExtra(RecognizerIntent.EXTRA_LANGUAGE, if (lang == "de") "de-DE" else "en-GB").putExtra(RecognizerIntent.EXTRA_PROMPT, speakPrompt)) }
            }) { Icon(Icons.Outlined.Mic, speakPrompt) }
            FilledIconButton(onClick = onSend, enabled = value.trim().length >= 3 && selected != null, modifier = Modifier.size(44.dp)) {
                Icon(Icons.Outlined.ArrowUpward, tr("Frage senden", "Send question"))
            }
        }
    }
}

/** "+" in the composer: scans or picks a file and adds it to the selected case; the server then reads its text. */
@Composable
fun rememberCaseUpload(state: AppState, case: CaseFile?): DocumentActions {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val done = tr("Zur Akte hinzugefügt – der Text wird jetzt erkannt.", "Added to the case – its text is being read now.")
    val failed = tr("Hochladen fehlgeschlagen.", "Upload failed.")
    val tooLarge = tr("Datei ist größer als 10 MB.", "File is larger than 10 MB.")
    return rememberDocumentActions(
        onFile = { file ->
            val target = case ?: return@rememberDocumentActions
            scope.launch {
                val text = try { state.api.uploadToCase(target.id, file.name, file.mime, file.bytes); state.refresh().join(); "${target.reference}: $done" }
                    catch (e: ApiException) { failed }
                Toast.makeText(context, text, Toast.LENGTH_LONG).show()
            }
        },
        onError = { Toast.makeText(context, if (it == "too_large") tooLarge else failed, Toast.LENGTH_LONG).show() },
    )
}

/** Earlier questions across all cases, newest first; tapping one opens that case's conversation. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HistorySheet(state: AppState, cases: List<CaseFile>, onOpen: (caseId: String) -> Unit, onDismiss: () -> Unit) {
    val lang = LocalLang.current
    var runs by remember { mutableStateOf<List<Pair<CaseFile, ResearchRun>>?>(null) }
    LaunchedEffect(cases) {
        runs = coroutineScope {
            cases.map { case -> async { runCatching { state.api.research(case.id) }.getOrDefault(emptyList()).map { case to it } } }.awaitAll()
        }.flatten().sortedByDescending { it.second.createdAt }.take(60)
    }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Text(tr("Frühere Fragen", "Earlier questions"), style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp))
        val list = runs
        when {
            list == null -> Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            list.isEmpty() -> Text(tr("Noch keine Fragen gestellt.", "No questions asked yet."), color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(20.dp))
            else -> LazyColumn(Modifier.padding(bottom = 24.dp)) {
                items(list, key = { it.second.id }) { (case, run) ->
                    Column(Modifier.fillMaxWidth().clickable { onOpen(case.id) }.padding(horizontal = 20.dp, vertical = 12.dp)) {
                        Text(run.question, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                        Text(case.reference + " · " + Dates.label(run.createdAt, lang), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}
