package de.schimmelpilz.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowDropDown
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
import de.schimmelpilz.app.data.CaseFile
import de.schimmelpilz.app.data.Dates
import de.schimmelpilz.app.data.Task
import de.schimmelpilz.app.ui.DateField
import de.schimmelpilz.app.ui.LocalLang
import de.schimmelpilz.app.ui.Pill
import de.schimmelpilz.app.ui.SectionLabel
import de.schimmelpilz.app.ui.errorText
import de.schimmelpilz.app.ui.theme.LocalBrand
import de.schimmelpilz.app.ui.tr
import kotlinx.coroutines.launch

/** One dated line: an open task (can be ticked off) or the deadline recorded in a case's particulars. */
private data class Due(val date: String?, val title: String, val case: CaseFile, val task: Task?)

@Composable
fun DeadlinesScreen(state: AppState, onOpenCase: (String) -> Unit) {
    val cases by state.cases.collectAsStateWithLifecycle()
    val lang = LocalLang.current
    var adding by remember { mutableStateOf(false) }
    val rows = cases.flatMap { c ->
        listOfNotNull(c.details.deadline?.let { Due(it, c.details.deadlineNote.ifBlank { tr("Frist aus den Stammdaten", "Deadline from case particulars") }, c, null) }) +
            c.tasks.filter { !it.completed }.map { Due(it.dueOn, it.title, c, it) }
    }.sortedBy { it.date ?: "9999" }
    val groups = listOf(
        tr("Überfällig", "Overdue") to rows.filter { (Dates.daysUntil(it.date) ?: 0) < 0 && it.date != null },
        tr("Nächste 10 Tage", "Next 10 days") to rows.filter { Dates.daysUntil(it.date)?.let { d -> d in 0..10 } == true },
        tr("Später", "Later") to rows.filter { (Dates.daysUntil(it.date) ?: -1) > 10 },
        tr("Ohne Datum", "No date") to rows.filter { it.date == null },
    ).filter { it.second.isNotEmpty() }

    Box(Modifier.fillMaxSize().statusBarsPadding()) {
        Column {
            ScreenTitle(tr("Fristen", "Deadlines")) {
                Text(tr("Heute, ", "Today, ") + Dates.label(Dates.today().toString(), lang), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            LazyColumn(contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (groups.isEmpty()) item { Text(tr("Keine offenen Fristen.", "No open deadlines."), color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 24.dp)) }
                groups.forEach { (label, items) ->
                    item { SectionLabel(label, Modifier.padding(top = 10.dp, bottom = 2.dp)) }
                    items(items, key = { (it.task?.id ?: "case-") + it.case.id }) { row -> DueRow(state, row, lang, onOpenCase) }
                }
            }
        }
        ExtendedFloatingActionButton(
            onClick = { adding = true }, icon = { Icon(Icons.Outlined.Add, null) }, text = { Text(tr("Frist / Aufgabe", "Deadline / task")) },
            modifier = Modifier.align(Alignment.BottomEnd).padding(16.dp),
        )
    }
    if (adding) TaskDialog(state, cases, presetCase = null, onDismiss = { adding = false })
}

@Composable
private fun DueRow(state: AppState, row: Due, lang: String, onOpenCase: (String) -> Unit) {
    val scope = rememberCoroutineScope()
    val brand = LocalBrand.current
    val days = Dates.daysUntil(row.date)
    val urgent = days != null && days <= 7
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(if (urgent) brand.warning else MaterialTheme.colorScheme.surfaceVariant)
            .clickable { onOpenCase(row.case.id) }.padding(start = 12.dp, top = 10.dp, bottom = 10.dp, end = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.size(width = 48.dp, height = 54.dp).clip(RoundedCornerShape(14.dp)).background(MaterialTheme.colorScheme.surface),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            if (row.date != null) {
                Text(Dates.weekday(row.date, lang), style = MaterialTheme.typography.labelSmall, color = if (urgent) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.primary)
                Text(Dates.toDate(row.date)!!.dayOfMonth.toString().padStart(2, '0'), style = MaterialTheme.typography.titleMedium, color = if (urgent) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.primary)
                Text(Dates.month(row.date, lang), style = MaterialTheme.typography.labelSmall, color = if (urgent) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.primary)
            } else Text("—")
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(row.title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(listOfNotNull(row.date?.let { Dates.label(it, lang) + " · " + Dates.relative(it, lang) }, row.case.reference).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (row.task?.priority == "high") Pill(tr("Hoch", "High"), MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer)
        if (row.task != null) Checkbox(checked = false, onCheckedChange = {
            scope.launch { runCatching { state.api.setTaskDone(row.task, true) }; state.refresh() }
        }) else Spacer(Modifier.width(12.dp))
    }
}

@Composable
fun TaskList(state: AppState, tasks: List<Task>, cases: List<CaseFile>, lang: String, onOpenCase: ((String) -> Unit)?) {
    val scope = rememberCoroutineScope()
    if (tasks.isEmpty()) { Text(tr("Keine Aufgaben.", "No tasks."), color = MaterialTheme.colorScheme.onSurfaceVariant); return }
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        tasks.forEach { task ->
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(MaterialTheme.colorScheme.surfaceVariant).padding(start = 14.dp, end = 4.dp, top = 6.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(task.title, style = MaterialTheme.typography.titleSmall, color = if (task.completed) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface)
                    Text(task.dueOn?.let { Dates.label(it, lang) + " · " + Dates.relative(it, lang) } ?: tr("Ohne Datum", "No date"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Checkbox(checked = task.completed, onCheckedChange = { done -> scope.launch { runCatching { state.api.setTaskDone(task, done) }; state.refresh() } })
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TaskDialog(state: AppState, cases: List<CaseFile>, presetCase: String?, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var caseId by remember { mutableStateOf(presetCase ?: cases.firstOrNull()?.id) }
    var title by remember { mutableStateOf("") }
    var due by remember { mutableStateOf("") }
    var high by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var open by remember { mutableStateOf(false) }
    val failed = errorText("")
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(tr("Frist / Aufgabe anlegen", "Add deadline / task")) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (presetCase == null) Box {
                    OutlinedButton(onClick = { open = true }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp)) {
                        Text(cases.firstOrNull { it.id == caseId }?.let { "${it.reference} · ${it.title}" } ?: tr("Akte wählen", "Choose case"),
                            Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Icon(Icons.Outlined.ArrowDropDown, null)
                    }
                    DropdownMenu(open, { open = false }) {
                        cases.forEach { c -> DropdownMenuItem(text = { Text("${c.reference} · ${c.title}", maxLines = 1, overflow = TextOverflow.Ellipsis) }, onClick = { caseId = c.id; open = false }) }
                    }
                }
                OutlinedTextField(title, { title = it }, label = { Text(tr("Aufgabe", "Task")) }, placeholder = { Text(tr("z. B. Klagefrist prüfen", "e.g. check filing deadline")) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                DateField(due, { due = it }, tr("Fällig am", "Due on"), Modifier.fillMaxWidth())
                FilterChip(selected = high, onClick = { high = !high }, label = { Text(tr("Hohe Priorität", "High priority")) })
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                Text(tr("Fristen werden manuell erfasst und nicht rechtlich geprüft.", "Deadlines are entered manually and not legally verified."),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        },
        confirmButton = {
            TextButton(enabled = !busy && caseId != null && title.trim().length >= 3, onClick = {
                busy = true; error = null
                scope.launch {
                    try { state.api.addTask(caseId!!, title, due, if (high) "high" else "normal"); state.refresh().join(); onDismiss() }
                    catch (e: ApiException) { error = failed }
                    finally { busy = false }
                }
            }) { Text(tr("Speichern", "Save")) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(tr("Abbrechen", "Cancel")) } },
    )
}
