package de.schimmelpilz.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.schimmelpilz.app.data.Dates
import de.schimmelpilz.app.ui.theme.Gold
import de.schimmelpilz.app.ui.theme.Green
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

val LocalLang = staticCompositionLocalOf { "de" }

/** German and English text side by side; the app language decides. */
@Composable
fun tr(de: String, en: String): String = if (LocalLang.current == "de") de else en

@Composable
fun ProvideLang(lang: String, content: @Composable () -> Unit) = CompositionLocalProvider(LocalLang provides lang, content = content)

/** The four-pointed spark of the Schimmelpilz assistant. */
@Composable
fun Spark(modifier: Modifier = Modifier, size: Dp = 24.dp, brush: Brush = Brush.linearGradient(listOf(Green, Color(0xFF2E7A5C), Gold))) {
    Canvas(modifier.size(size)) {
        val w = this.size.width; val c = w / 2f
        val path = Path().apply {
            moveTo(c, 0.05f * w)
            cubicTo(c + 0.034f * w, 0.34f * w, c + 0.16f * w, 0.466f * w, 0.95f * w, c)
            cubicTo(c + 0.16f * w, 0.534f * w, c + 0.034f * w, 0.66f * w, c, 0.95f * w)
            cubicTo(c - 0.034f * w, 0.66f * w, c - 0.16f * w, 0.534f * w, 0.05f * w, c)
            cubicTo(c - 0.16f * w, 0.466f * w, c - 0.034f * w, 0.34f * w, c, 0.05f * w)
            close()
        }
        drawPath(path, brush)
    }
}

@Composable
fun Avatar(initials: String, size: Dp = 40.dp, modifier: Modifier = Modifier) {
    Box(modifier.size(size).clip(CircleShape).background(Brush.linearGradient(listOf(Green, Gold))), contentAlignment = Alignment.Center) {
        Text(initials.ifBlank { "S" }, color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = (size.value * 0.36f).sp)
    }
}

@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(text.uppercase(), modifier, style = MaterialTheme.typography.labelMedium.copy(letterSpacing = 0.8.sp), color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
fun Pill(text: String, container: Color, content: Color, modifier: Modifier = Modifier) {
    Text(
        text, modifier.clip(RoundedCornerShape(10.dp)).background(container).padding(PaddingValues(horizontal = 10.dp, vertical = 4.dp)),
        color = content, style = MaterialTheme.typography.labelMedium,
    )
}

@Composable
fun statusPill(status: String): Pair<String, Pair<Color, Color>> = when (status) {
    "waiting" -> tr("Wartet", "Waiting") to (de.schimmelpilz.app.ui.theme.LocalBrand.current.warning to de.schimmelpilz.app.ui.theme.LocalBrand.current.onWarning)
    "closed" -> tr("Abgeschlossen", "Closed") to (MaterialTheme.colorScheme.surfaceVariant to MaterialTheme.colorScheme.onSurfaceVariant)
    else -> tr("In Bearbeitung", "Active") to (MaterialTheme.colorScheme.primaryContainer to MaterialTheme.colorScheme.onPrimaryContainer)
}

@Composable
fun legalAreaLabel(area: String): String = when (area) {
    "consumer" -> tr("Verbraucherrecht", "Consumer law")
    "tenancy" -> tr("Mietrecht", "Tenancy law")
    "contract" -> tr("Vertragsrecht", "Contract law")
    "commercial" -> tr("Handelsrecht", "Commercial law")
    "employment" -> tr("Arbeitsrecht", "Employment law")
    "family" -> tr("Familienrecht", "Family law")
    "social" -> tr("Sozialrecht", "Social law")
    "administrative" -> tr("Verwaltungsrecht", "Administrative law")
    "criminal" -> tr("Strafrecht", "Criminal law")
    else -> tr("Allgemein", "General")
}

@Composable
fun errorText(detail: String): String = when (detail) {
    "network" -> tr("Keine Verbindung zum Server. Bitte prüfen Sie Ihre Internetverbindung.", "No connection to the server. Please check your internet connection.")
    "ai_unavailable" -> tr("Der KI-Assistent ist gerade nicht erreichbar. Bitte später erneut versuchen.", "The AI assistant is currently unavailable. Please try again later.")
    "ai_busy" -> tr("Der Assistent beantwortet gerade eine andere Frage. Bitte gleich noch einmal senden.", "The assistant is answering another question. Please send again in a moment.")
    "ai_paused_by_operator" -> tr("KI-Anfragen sind vom Betreiber pausiert.", "AI requests are paused by the operator.")
    "subscription_required_read_export_remains_available" -> tr("Für Änderungen ist ein aktiver Zugang nötig. Lesen bleibt möglich.", "Editing needs active access. Reading remains available.")
    else -> tr("Das hat nicht geklappt. Bitte erneut versuchen.", "That did not work. Please try again.") + if (detail.isNotBlank()) " ($detail)" else ""
}

/** Date entry in TT.MM.JJJJ with the system calendar as an alternative; value and onChange use ISO. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DateField(iso: String, onChange: (String) -> Unit, label: String, modifier: Modifier = Modifier) {
    val lang = LocalLang.current
    var text by remember(iso) { mutableStateOf(Dates.label(iso.ifBlank { null }, lang).takeIf { iso.isNotBlank() } ?: "") }
    var invalid by remember { mutableStateOf(false) }
    var picking by remember { mutableStateOf(false) }
    OutlinedTextField(
        value = text,
        onValueChange = { value ->
            text = value
            val parsed = Dates.parseInput(value)
            invalid = parsed == null
            if (parsed != null) onChange(parsed)
        },
        label = { Text(label) },
        placeholder = { Text(if (lang == "de") "TT.MM.JJJJ" else "DD/MM/YYYY") },
        isError = invalid,
        supportingText = if (invalid) { { Text(tr("Bitte Datum als TT.MM.JJJJ eingeben.", "Enter the date as DD/MM/YYYY.")) } } else null,
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        trailingIcon = { IconButton(onClick = { picking = true }) { Icon(Icons.Outlined.CalendarMonth, tr("Kalender öffnen", "Open calendar")) } },
        modifier = modifier,
    )
    if (picking) {
        val initial = Dates.toDate(iso)?.atStartOfDay()?.toInstant(ZoneOffset.UTC)?.toEpochMilli()
        val state = rememberDatePickerState(initialSelectedDateMillis = initial)
        DatePickerDialog(
            onDismissRequest = { picking = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let { millis ->
                        val picked = Instant.ofEpochMilli(millis).atZone(ZoneOffset.UTC).toLocalDate().toString()
                        text = Dates.label(picked, lang); invalid = false; onChange(picked)
                    }
                    picking = false
                }) { Text("OK") }
            },
            dismissButton = { TextButton(onClick = { picking = false }) { Text(tr("Abbrechen", "Cancel")) } },
        ) { DatePicker(state) }
    }
}

fun LocalDate.iso(): String = toString()

@Composable
fun Dot(color: Color, size: Dp = 8.dp) = Canvas(Modifier.size(size)) { drawCircle(color, radius = this.size.minDimension / 2, center = Offset(this.size.width / 2, this.size.height / 2)) }
