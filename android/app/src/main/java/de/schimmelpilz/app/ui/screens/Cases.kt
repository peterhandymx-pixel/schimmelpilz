package de.schimmelpilz.app.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import de.schimmelpilz.app.AppState
import de.schimmelpilz.app.data.CaseFile
import de.schimmelpilz.app.data.Dates
import de.schimmelpilz.app.ui.LocalLang
import de.schimmelpilz.app.ui.Pill
import de.schimmelpilz.app.ui.legalAreaLabel
import de.schimmelpilz.app.ui.statusPill
import de.schimmelpilz.app.ui.theme.LocalBrand
import de.schimmelpilz.app.ui.tr
import kotlinx.coroutines.launch

fun CaseFile.matches(query: String): Boolean {
    val text = listOf(reference, title, description, details.clientName, details.opponentName, details.court).joinToString(" ").lowercase()
    return query.trim().lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }.all { it in text }
}

@Composable
fun ScreenTitle(text: String, trailing: @Composable () -> Unit = {}) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.weight(1f)); trailing()
    }
}

@Composable
fun CasesScreen(state: AppState, onOpen: (String) -> Unit, onOpenDeadlines: () -> Unit) {
    val cases by state.cases.collectAsStateWithLifecycle()
    val lang = LocalLang.current
    var query by remember { mutableStateOf("") }
    var filter by remember { mutableStateOf("all") }
    var refreshing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val shown = cases.filter { (filter == "all" || it.details.status == filter) && it.matches(query) }
    val week = cases.count { c -> c.nextDue?.first?.let { Dates.daysUntil(it) }?.let { it in 0..7 } == true }

    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        ScreenTitle(tr("Akten", "Cases"))
        PullToRefreshBox(isRefreshing = refreshing, onRefresh = { scope.launch { refreshing = true; state.refresh().join(); refreshing = false } }) {
            LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                item {
                    TextField(
                        query, { query = it }, leadingIcon = { Icon(Icons.Outlined.Search, null) },
                        placeholder = { Text(tr("Aktenzeichen, Name, Gericht …", "Reference, name, court …")) }, singleLine = true,
                        shape = RoundedCornerShape(50),
                        colors = TextFieldDefaults.colors(focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent,
                            focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant, unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Stat("${cases.size}", tr("Offene Akten", "Open cases"), Modifier.weight(1f)) { query = ""; filter = "all" }
                        Stat("$week", tr("Fristen 7 Tage", "Due in 7 days"), Modifier.weight(1f), warn = week > 0, onClick = onOpenDeadlines)
                        Stat("${cases.sumOf { c -> c.tasks.count { !it.completed } }}", tr("Aufgaben", "Tasks"), Modifier.weight(1f), onClick = onOpenDeadlines)
                        Stat("${cases.sumOf { it.documents.size }}", tr("Dokumente", "Documents"), Modifier.weight(1f), onClick = null)
                    }
                }
                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("all" to tr("Alle", "All"), "active" to tr("In Bearbeitung", "Active"), "waiting" to tr("Wartet", "Waiting")).forEach { (id, label) ->
                            FilterChip(selected = filter == id, onClick = { filter = id }, label = { Text(label) })
                        }
                    }
                }
                if (shown.isEmpty()) item {
                    Text(if (cases.isEmpty()) tr("Noch keine Akten. Legen Sie Akten in der Web-App an; sie erscheinen hier automatisch.", "No cases yet. Create cases in the web app; they appear here automatically.")
                    else tr("Keine Akte passt zur Suche.", "No case matches your search."), color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 24.dp))
                }
                items(shown, key = { it.id }) { item -> CaseCard(item, lang) { onOpen(item.id) } }
                item { Spacer(Modifier.height(12.dp)) }
            }
        }
    }
}

@Composable
private fun Stat(value: String, label: String, modifier: Modifier, warn: Boolean = false, onClick: (() -> Unit)?) {
    val brand = LocalBrand.current
    Column(
        modifier.clip(RoundedCornerShape(16.dp)).background(if (warn) brand.warning else MaterialTheme.colorScheme.surfaceVariant)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier).padding(vertical = 10.dp, horizontal = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(value, style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold), color = if (warn) brand.onWarning else MaterialTheme.colorScheme.onSurface)
        Text(label, style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Medium), color = if (warn) brand.onWarning else MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
    }
}

@Composable
fun CaseCard(item: CaseFile, lang: String, onClick: () -> Unit) {
    val (statusText, colors) = statusPill(item.details.status)
    Surface(onClick = onClick, shape = RoundedCornerShape(20.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(item.reference, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary, modifier = Modifier.weight(1f))
                Pill(statusText, colors.first, colors.second)
            }
            Text(item.title, style = MaterialTheme.typography.titleMedium)
            val parties = listOf(item.details.clientName, item.details.opponentName).filter { it.isNotBlank() }.joinToString(" ./. ")
            Text(listOf(parties, legalAreaLabel(item.details.legalArea)).filter { it.isNotBlank() }.joinToString(" · "),
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            item.nextDue?.let { (date, _) ->
                val overdue = (Dates.daysUntil(date) ?: 0) < 0
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.CalendarMonth, null, Modifier.size(15.dp), tint = if (overdue || (Dates.daysUntil(date) ?: 99) <= 7) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.width(6.dp))
                    Text(tr("Frist ", "Due ") + Dates.label(date, lang) + " · " + Dates.relative(date, lang), style = MaterialTheme.typography.labelLarge,
                        color = if (overdue || (Dates.daysUntil(date) ?: 99) <= 7) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}
