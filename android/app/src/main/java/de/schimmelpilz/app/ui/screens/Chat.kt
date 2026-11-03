package de.schimmelpilz.app.ui.screens

import android.content.ClipData
import android.content.Intent
import android.widget.Toast
import androidx.core.content.FileProvider
import java.io.File
import androidx.core.net.toUri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.OpenInNew
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.PictureAsPdf
import androidx.compose.material.icons.outlined.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.ClipEntry
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import de.schimmelpilz.app.AppState
import de.schimmelpilz.app.data.ApiException
import de.schimmelpilz.app.data.Dates
import de.schimmelpilz.app.data.LegalSource
import de.schimmelpilz.app.data.ResearchRun
import de.schimmelpilz.app.ui.LocalLang
import de.schimmelpilz.app.ui.Spark
import de.schimmelpilz.app.ui.errorText
import de.schimmelpilz.app.ui.theme.LocalBrand
import de.schimmelpilz.app.ui.tr
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(state: AppState, caseId: String, initialQuestion: String, onBack: () -> Unit, onOpenCase: (String) -> Unit) {
    val cases by state.cases.collectAsStateWithLifecycle()
    val lang = LocalLang.current
    val scope = rememberCoroutineScope()
    val runs = remember { mutableStateListOf<ResearchRun>() }
    var pending by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var input by remember { mutableStateOf("") }
    var source by remember { mutableStateOf<LegalSource?>(null) }
    var currentCase by remember { mutableStateOf(caseId) }
    val case = cases.firstOrNull { it.id == currentCase }
    val list = rememberLazyListState()
    val context = LocalContext.current
    var exporting by remember { mutableStateOf(false) }
    val exportFailed = tr("Export hat nicht geklappt. Bitte erneut versuchen.", "Export failed. Please try again.")

    /** Fetches the answer as PDF or Word from the server and hands it to the share sheet (mail, Drive, WhatsApp …). */
    fun export(run: ResearchRun, extension: String) {
        if (exporting) return
        exporting = true
        scope.launch {
            try {
                val name = "Schimmelpilz-Recherche-${case?.reference ?: "Antwort"}.$extension"
                val file = state.api.download("api/cases/$currentCase/research/${run.id}/answer.$extension?lang=$lang", File(context.cacheDir, "exports/$name"))
                val uri = FileProvider.getUriForFile(context, context.packageName + ".files", file)
                val mime = if (extension == "pdf") "application/pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                val send = Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                context.startActivity(Intent.createChooser(send, name))
            } catch (e: ApiException) {
                Toast.makeText(context, exportFailed, Toast.LENGTH_LONG).show()
            } finally { exporting = false }
        }
    }

    fun send(question: String) {
        if (question.trim().length < 3 || pending != null) return
        pending = question.trim(); error = null
        scope.launch {
            try { runs += state.api.ask(currentCase, question.trim(), lang) }
            catch (e: ApiException) { error = e.detail; input = question }
            finally { pending = null }
        }
    }

    LaunchedEffect(currentCase) {
        runs.clear()
        runCatching { state.api.research(currentCase) }.onSuccess { history -> runs += history.filter { it.status == "completed" } }
        if (initialQuestion.isNotBlank() && currentCase == caseId && runs.none { it.question == initialQuestion }) send(initialQuestion)
    }
    LaunchedEffect(runs.size, pending) { val count = runs.size + (if (pending != null) 1 else 0); if (count > 0) list.animateScrollToItem(count - 1) }

    val errorMessage = error?.let { errorText(it) }
    Column(Modifier.fillMaxSize().statusBarsPadding().imePadding()) {
        Row(Modifier.fillMaxWidth().padding(4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, tr("Zurück", "Back")) }
            Column(Modifier.weight(1f).clickable(enabled = case != null) { case?.let { onOpenCase(it.id) } }) {
                Text(case?.title ?: tr("Recherche", "Research"), style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                case?.let { Text(tr("Akte ", "Case ") + it.reference, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary) }
            }
        }
        LazyColumn(Modifier.weight(1f).fillMaxWidth(), state = list, contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 20.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(22.dp)) {
            if (runs.isEmpty() && pending == null) item {
                Text(tr("Stellen Sie eine Frage zu dieser Akte. Die Antwort nennt die Gesetze, auf die sie sich stützt.",
                    "Ask a question about this case. The answer names the statutes it relies on."),
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 24.dp))
            }
            items(runs, key = { it.id }) { run ->
                Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Question(run.question)
                    Answer(run, onSource = { source = it }, exporting = exporting, onExport = { ext -> export(run, ext) })
                }
            }
            pending?.let { question ->
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                        Question(question)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Spark(size = 26.dp); Spacer(Modifier.size(12.dp))
                            Column(Modifier.weight(1f)) {
                                Text(tr("Schimmelpilz sucht passende Gesetze und formuliert die Antwort …", "Schimmelpilz is finding relevant statutes and writing the answer …"), style = MaterialTheme.typography.bodyMedium)
                                Spacer(Modifier.height(8.dp)); LinearProgressIndicator(Modifier.fillMaxWidth())
                            }
                        }
                    }
                }
            }
            errorMessage?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        }
        Composer(
            value = input, onValue = { input = it }, cases = cases, selected = case, onSelect = { currentCase = it },
            onSend = { val q = input; input = ""; send(q) }, placeholder = tr("Nachfrage stellen", "Ask a follow-up"), attach = rememberCaseUpload(state, case),
        )
    }

    source?.let { item ->
        ModalBottomSheet(onDismissRequest = { source = null }) { SourceSheet(item) }
    }
}

@Composable
private fun Question(text: String) {
    Row(Modifier.fillMaxWidth()) {
        Spacer(Modifier.weight(1f))
        Text(
            text, Modifier.widthIn(max = 300.dp).clip(RoundedCornerShape(22.dp, 22.dp, 6.dp, 22.dp)).background(MaterialTheme.colorScheme.surfaceVariant).padding(horizontal = 16.dp, vertical = 12.dp),
            style = MaterialTheme.typography.bodyLarge,
        )
    }
}

/** Light formatting of model output: **bold**, bullet lines; everything else stays plain text. */
fun formatAnswer(text: String): AnnotatedString = buildAnnotatedString {
    text.trim().lines().forEachIndexed { index, raw ->
        if (index > 0) append("\n")
        val line = raw.trimEnd().let { if (it.startsWith("- ") || it.startsWith("* ")) "•  " + it.drop(2) else it }.removePrefix("### ").removePrefix("## ").removePrefix("# ")
        var rest = line
        while (true) {
            val start = rest.indexOf("**"); val end = if (start >= 0) rest.indexOf("**", start + 2) else -1
            if (start < 0 || end < 0) { append(rest); break }
            append(rest.substring(0, start))
            withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append(rest.substring(start + 2, end)) }
            rest = rest.substring(end + 2)
        }
    }
}

@Composable
private fun Answer(run: ResearchRun, onSource: (LegalSource) -> Unit, exporting: Boolean, onExport: (String) -> Unit) {
    val context = LocalContext.current
    val clipboard = LocalClipboard.current
    val scope = rememberCoroutineScope()
    val lang = LocalLang.current
    val answer = run.answer.orEmpty()
    Row {
        Spark(size = 26.dp, modifier = Modifier.padding(top = 2.dp))
        Spacer(Modifier.size(12.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(formatAnswer(answer), style = MaterialTheme.typography.bodyLarge)
            if (run.legalSources.isNotEmpty()) {
                Text(tr("Quellen", "Sources"), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(run.legalSources) { item ->
                        Column(
                            Modifier.widthIn(max = 220.dp).clip(RoundedCornerShape(16.dp)).background(MaterialTheme.colorScheme.surfaceVariant).clickable { onSource(item) }.padding(12.dp),
                        ) {
                            Text(item.title.substringBefore(" · "), style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
                            Text(item.title.substringAfter(" · ", ""), style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            Text(
                tr("Allgemeine Information, ", "General information, ") + Dates.labelWithTime(run.createdAt, lang) +
                    tr(". Für Ihren konkreten Fall: Anwältin, Anwalt oder Beratungsstelle.", ". For your specific case: a lawyer or advice centre."),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row {
                IconButton(onClick = { scope.launch { clipboard.setClipEntry(ClipEntry(ClipData.newPlainText("Schimmelpilz", answer))) } }) {
                    Icon(Icons.Outlined.ContentCopy, tr("Antwort kopieren", "Copy answer"))
                }
                IconButton(onClick = {
                    context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, "${run.question}\n\n$answer"), null))
                }) { Icon(Icons.Outlined.Share, tr("Teilen", "Share")) }
                IconButton(enabled = !exporting, onClick = { onExport("pdf") }) { Icon(Icons.Outlined.PictureAsPdf, tr("Als PDF teilen", "Share as PDF")) }
                IconButton(enabled = !exporting, onClick = { onExport("docx") }) { Icon(Icons.Outlined.Description, tr("Als Word-Datei teilen", "Share as Word file")) }
            }
        }
    }
}

@Composable
private fun SourceSheet(item: LegalSource) {
    val context = LocalContext.current
    val lang = LocalLang.current
    Column(Modifier.fillMaxWidth().padding(horizontal = 22.dp).padding(bottom = 28.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(item.title.substringBefore(" · "), style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
        Text(item.title.substringAfter(" · ", ""), style = MaterialTheme.typography.titleSmall)
        Text(listOfNotNull(item.pinpoint.ifBlank { null }, item.fetchedAt?.let { tr("Abgerufen ", "Retrieved ") + Dates.label(it, lang) }).joinToString(" · "),
            style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(item.text + if (item.truncated) " …" else "", style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.clip(RoundedCornerShape(16.dp)).background(LocalBrand.current.warning.copy(alpha = 0.6f)).padding(14.dp))
        if (item.url.isNotBlank()) Button(onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, item.url.toUri())) }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.AutoMirrored.Outlined.OpenInNew, null, Modifier.size(18.dp)); Spacer(Modifier.size(8.dp)); Text(tr("Original öffnen", "Open original"))
        }
        Text(tr("Wortlaut aus der amtlichen Quelle; die rechtliche Bewertung prüfen Sie selbst.", "Wording from the official source; check the legal assessment yourself."),
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
