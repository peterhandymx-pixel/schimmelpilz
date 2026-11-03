package de.schimmelpilz.app.ui.screens

import de.schimmelpilz.app.ui.errorText
import androidx.compose.material.icons.outlined.DeleteForever
import de.schimmelpilz.app.data.ApiException
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.foundation.text.KeyboardOptions
import kotlinx.coroutines.launch
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.AlertDialog
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.automirrored.outlined.OpenInNew
import androidx.compose.material.icons.outlined.Balance
import androidx.compose.material.icons.outlined.Contacts
import androidx.compose.material.icons.outlined.EditNote
import androidx.compose.material.icons.outlined.Groups
import androidx.compose.material.icons.outlined.Language
import androidx.compose.material.icons.automirrored.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.NotificationsActive
import androidx.compose.material.icons.outlined.Public
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Switch
import androidx.compose.foundation.layout.heightIn
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.Hyphens
import androidx.compose.ui.text.style.LineBreak
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.Manifest
import de.schimmelpilz.app.Reminders
import de.schimmelpilz.app.data.Team
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import de.schimmelpilz.app.AppState
import de.schimmelpilz.app.BuildConfig
import de.schimmelpilz.app.ThemeMode
import de.schimmelpilz.app.data.Billing
import de.schimmelpilz.app.data.Dates
import de.schimmelpilz.app.ui.Avatar
import de.schimmelpilz.app.ui.LocalLang
import de.schimmelpilz.app.ui.SectionLabel
import de.schimmelpilz.app.ui.BRAND
import de.schimmelpilz.app.ui.BrandLockup
import de.schimmelpilz.app.ui.tr

@Composable
fun MoreScreen(state: AppState) {
    val user by state.user.collectAsStateWithLifecycle()
    val theme by state.themeMode.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val lang = LocalLang.current
    var billing by remember { mutableStateOf<Billing?>(null) }
    var deleting by remember { mutableStateOf(false) }
    var team by remember { mutableStateOf<Team?>(null) }
    var switching by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { billing = runCatching { state.api.billing() }.getOrNull() }
    LaunchedEffect(Unit) { team = runCatching { state.api.team() }.getOrNull() }
    val current = team?.workspaces?.firstOrNull { it.ownerId == team?.selected }
    if (switching) team?.let { t -> WorkspaceDialog(state, t, onDone = { changed -> switching = false; if (changed != null) team = changed }) }
    if (deleting) DeleteAccountDialog(state, user?.mfaEnabled == true, onDismiss = { deleting = false })

    Column(Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        ScreenTitle(tr("Mehr", "More"))
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(MaterialTheme.colorScheme.surfaceVariant).padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Avatar(user?.initials ?: "", size = 48.dp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(user?.fullName ?: "", style = MaterialTheme.typography.titleMedium)
                Text(listOfNotNull(current?.name?.ifBlank { null } ?: user?.organisation?.ifBlank { null }, user?.email).joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            // Only someone invited into another workspace has anything to switch to.
            if ((team?.workspaces?.size ?: 0) > 1) OutlinedButton(onClick = { switching = true }) { Text(tr("Wechseln", "Switch")) }
        }

        SectionLabel(tr("In der Web-App", "In the web app"))
        Text(tr("Diese Bereiche öffnen sich im Browser, mit demselben Konto.", "These sections open in the browser with the same account."),
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        ModuleGrid(listOf(
            Module(Icons.Outlined.Contacts, tr("Adressen", "Addresses"), "parties", Color(0xFF3F6F93)),
            Module(Icons.Outlined.EditNote, tr("Schrift\u00ADverkehr", "Corres\u00ADpondence"), "drafts", Color(0xFF4A6AA0)),
            Module(Icons.Outlined.Description, tr("E-Akte", "E-files"), "documents", Color(0xFFC4613F)),
            Module(Icons.AutoMirrored.Outlined.ReceiptLong, tr("Kosten\u00ADprüfung", "Cost review"), "costs", Color(0xFFA8813F)),
            Module(Icons.Outlined.Balance, tr("Verfahrens\u00ADwege", "Procedural routes"), "routes", Color(0xFF8A6538)),
            Module(Icons.Outlined.Public, tr("Online Services", "Online services"), "services", Color(0xFF2F6F8F)),
        )) { section -> openWeb(context, "?open=$section") }
        Links(listOf(
            Triple(Icons.Outlined.Groups, tr("Team & Rechte", "Team & access"), "team"),
            Triple(Icons.Outlined.Settings, tr("Profil, Briefpapier & Sicherheit", "Profile, letter paper & security"), "account"),
        )) { section -> openWeb(context, "?open=$section") }

        SectionLabel(tr("Abonnement", "Subscription"))
        Surface(shape = RoundedCornerShape(20.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
            Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                val b = billing
                Text(when (b?.effectiveStatus) {
                    "pilot" -> tr("Kostenloser Pilotzugang", "Free pilot access")
                    "trial" -> tr("Testphase bis ", "Trial until ") + Dates.label(b.trialEnd, lang)
                    "active" -> tr("Aktiv bis ", "Active until ") + Dates.label(b.periodEnd, lang)
                    "past_due" -> tr("Zahlung fehlgeschlagen – bitte Zahlungsmittel aktualisieren", "Payment failed – please update your payment method")
                    null -> "…"
                    else -> tr("Kein aktiver Zugang – Lesen bleibt möglich", "No active access – reading remains available")
                }, style = MaterialTheme.typography.titleSmall)
                Text(tr("Abos verwalten Sie derzeit in der Web-App.", "Subscriptions are currently managed in the web app."), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                TextButton(onClick = { openWeb(context, "?open=billing") }, contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)) { Text(tr("Abo öffnen", "Open subscription")) }
            }
        }

        SectionLabel(tr("Erinnerungen", "Reminders"))
        ReminderSwitch()

        SectionLabel(tr("Darstellung", "Appearance"))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Outlined.Language, null); Spacer(Modifier.width(12.dp))
            Text(tr("Sprache", "Language"), Modifier.weight(1f))
            LanguageSwitch(state, Modifier.width(140.dp))
        }
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf(ThemeMode.System to tr("System", "System"), ThemeMode.Light to tr("Hell", "Light"), ThemeMode.Dark to tr("Dunkel", "Dark")).forEachIndexed { index, (mode, label) ->
                SegmentedButton(theme == mode, { state.setTheme(mode) }, SegmentedButtonDefaults.itemShape(index, 3)) { Text(label) }
            }
        }
        TextButton(onClick = { state.signOut() }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.AutoMirrored.Outlined.Logout, null, tint = MaterialTheme.colorScheme.error); Spacer(Modifier.width(8.dp))
            Text(tr("Abmelden", "Sign out"), color = MaterialTheme.colorScheme.error)
        }
        TextButton(onClick = { deleting = true }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Outlined.DeleteForever, null, tint = MaterialTheme.colorScheme.error); Spacer(Modifier.width(8.dp))
            Text(tr("Konto löschen", "Delete account"), color = MaterialTheme.colorScheme.error)
        }
        BrandLockup(Modifier.padding(top = 8.dp), scale = 0.85f, fullWidth = 240.dp)
        Text("$BRAND ${BuildConfig.VERSION_NAME} · " + tr("Allgemeine Rechtsinformation, keine anwaltliche Beratung im Einzelfall.", "General legal information, not individual legal advice."),
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 24.dp))
    }
}

private class Module(val icon: ImageVector, val label: String, val section: String, val tint: Color)

@Composable
private fun ModuleGrid(modules: List<Module>, onOpen: (section: String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        modules.chunked(3).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { module ->
                    Surface(onClick = { onOpen(module.section) }, shape = RoundedCornerShape(20.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                        modifier = Modifier.weight(1f).heightIn(min = 92.dp)) {
                        Column(Modifier.padding(horizontal = 6.dp, vertical = 14.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Icon(module.icon, null, Modifier.size(28.dp), tint = module.tint)
                            Text(module.label, style = MaterialTheme.typography.labelLarge.copy(hyphens = Hyphens.Auto, lineBreak = LineBreak.Paragraph), textAlign = TextAlign.Center, maxLines = 2)
                        }
                    }
                }
            }
        }
    }
}

/** Daily deadline reminders; on Android 13+ switching them on asks for the notification permission. */
@Composable
private fun ReminderSwitch() {
    val context = LocalContext.current
    var on by remember { mutableStateOf(Reminders.enabled(context) && !Reminders.permissionNeeded(context)) }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        on = granted; Reminders.setEnabled(context, granted)
    }
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Outlined.NotificationsActive, null); Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(tr("Fristen-Erinnerungen", "Deadline reminders"))
            Text(tr("Morgens: 2 Tage vorher, am Vortag, am Fristtag und bei Überfälligkeit.", "Mornings: 2 days before, the day before, on the day and when overdue."),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = on, onCheckedChange = { want ->
            if (want && Reminders.permissionNeeded(context)) ask.launch(Manifest.permission.POST_NOTIFICATIONS)
            else { on = want; Reminders.setEnabled(context, want) }
        })
    }
}

@Composable
private fun WorkspaceDialog(state: AppState, team: Team, onDone: (Team?) -> Unit) {
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val failed = tr("Wechsel nicht möglich. Bitte erneut versuchen.", "Could not switch. Please try again.")
    AlertDialog(
        onDismissRequest = { if (!busy) onDone(null) },
        title = { Text(tr("Arbeitsbereich wechseln", "Switch workspace")) },
        text = {
            Column {
                team.workspaces.forEach { workspace ->
                    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).clickable(enabled = !busy) {
                        busy = true
                        scope.launch {
                            try {
                                state.api.switchWorkspace(workspace.ownerId)
                                val updated = state.api.team()
                                state.refresh().join()
                                onDone(updated)
                            } catch (e: ApiException) { error = failed; busy = false }
                        }
                    }.padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(selected = workspace.ownerId == team.selected, onClick = null)
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text(workspace.name?.ifBlank { null } ?: tr("Eigener Arbeitsbereich", "Own workspace"), style = MaterialTheme.typography.titleSmall)
                            Text(roleLabel(workspace.role), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = { TextButton(enabled = !busy, onClick = { onDone(null) }) { Text(tr("Schließen", "Close")) } },
    )
}

@Composable
private fun roleLabel(role: String) = when (role) {
    "owner" -> tr("Inhaber/in", "Owner")
    "editor" -> tr("Bearbeiten", "Editor")
    "viewer" -> tr("Nur lesen", "Read only")
    "operator" -> tr("Betrieb", "Operator")
    else -> role
}

@Composable
private fun Links(rows: List<Triple<ImageVector, String, String>>, onClick: (section: String) -> Unit) {
    Surface(shape = RoundedCornerShape(20.dp), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column {
            rows.forEachIndexed { index, (icon, label, section) ->
                Row(Modifier.fillMaxWidth().clickable { onClick(section) }.padding(horizontal = 16.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(icon, null, tint = MaterialTheme.colorScheme.primary); Spacer(Modifier.width(14.dp))
                    Text(label, Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                    Icon(Icons.AutoMirrored.Outlined.OpenInNew, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (index < rows.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
        }
    }
}

/** Permanent deletion of the account and all its data, confirmed with the password (and code), as Google Play requires in-app. */
@Composable
private fun DeleteAccountDialog(state: AppState, mfa: Boolean, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    val word = tr("LÖSCHEN", "DELETE")
    var password by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf("") }
    var needsCode by remember { mutableStateOf(mfa) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val messages = mapOf(
        "password_incorrect" to tr("Das Passwort ist nicht korrekt.", "The password is incorrect."),
        "mfa_code_required" to tr("Bitte den Bestätigungscode aus der Authenticator-App eingeben.", "Please enter the code from your authenticator app."),
        "cancel_subscription_first" to tr("Bitte zuerst das laufende Abo in der Web-App kündigen.", "Please cancel the running subscription in the web app first."),
        "last_administrator" to tr("Das letzte Administratorkonto kann nicht gelöscht werden.", "The last administrator account cannot be deleted."),
    )
    val generic = errorText("")
    val offline = errorText("network")
    AlertDialog(
        onDismissRequest = { if (!busy) onDismiss() },
        icon = { Icon(Icons.Outlined.DeleteForever, null, tint = MaterialTheme.colorScheme.error) },
        title = { Text(tr("Konto endgültig löschen?", "Delete account permanently?")) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(tr("Gelöscht werden Ihr Konto mit allen Akten, Dokumenten, Entwürfen, Fristen, Recherchen, Kontakten und Posteingängen. Das kann nicht rückgängig gemacht werden. Laden Sie vorher in der Web-App herunter, was Sie aufbewahren müssen.",
                    "This deletes your account with all cases, documents, drafts, deadlines, research, contacts and inbox items. It cannot be undone. Download anything you must keep in the web app first."),
                    style = MaterialTheme.typography.bodyMedium)
                OutlinedTextField(password, { password = it }, label = { Text(tr("Passwort", "Password")) }, singleLine = true,
                    visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password), modifier = Modifier.fillMaxWidth())
                if (needsCode) OutlinedTextField(code, { code = it.trim() }, label = { Text(tr("Bestätigungscode", "Verification code")) }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth())
                OutlinedTextField(confirm, { confirm = it }, label = { Text(tr("Zur Bestätigung $word eingeben", "Type $word to confirm")) }, singleLine = true, modifier = Modifier.fillMaxWidth())
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
            }
        },
        confirmButton = {
            TextButton(enabled = !busy && password.isNotEmpty() && confirm.trim() == word && (!needsCode || code.isNotBlank()), onClick = {
                busy = true; error = null
                scope.launch {
                    try {
                        state.api.deleteAccount(password, word, code)
                        state.accountDeleted()
                    } catch (e: ApiException) {
                        if (e.detail == "mfa_code_required") needsCode = true
                        error = messages[e.detail] ?: if (e.status == 0) offline else generic
                    } finally { busy = false }
                }
            }) { Text(tr("Endgültig löschen", "Delete permanently"), color = MaterialTheme.colorScheme.error) }
        },
        dismissButton = { TextButton(enabled = !busy, onClick = onDismiss) { Text(tr("Abbrechen", "Cancel")) } },
    )
}
