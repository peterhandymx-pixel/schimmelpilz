package de.schimmelpilz.app.ui.screens

import android.content.Intent
import androidx.core.net.toUri
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.Dns
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import de.schimmelpilz.app.AppState
import de.schimmelpilz.app.Server
import de.schimmelpilz.app.R
import de.schimmelpilz.app.data.ApiException
import de.schimmelpilz.app.ui.LoginLockup
import de.schimmelpilz.app.ui.WelcomeLockup
import de.schimmelpilz.app.ui.errorText
import de.schimmelpilz.app.ui.tr
import kotlinx.coroutines.launch

/** Opens a page of the web app (registration, password reset, office modules) in the browser. */
fun openWeb(context: android.content.Context, path: String = "") {
    context.startActivity(Intent(Intent.ACTION_VIEW, (Server.url(context).trimEnd('/') + "/" + path.trimStart('/')).toUri()))
}

@Composable
fun LanguageSwitch(state: AppState, modifier: Modifier = Modifier) {
    val lang by state.lang.collectAsState()
    SingleChoiceSegmentedButtonRow(modifier) {
        listOf("de" to "DE", "en" to "EN").forEachIndexed { index, (code, label) ->
            SegmentedButton(
                selected = lang == code, onClick = { state.setLang(code) },
                shape = SegmentedButtonDefaults.itemShape(index, 2), icon = {},
            ) { Text(label) }
        }
    }
}

@Composable
fun WelcomeScreen(state: AppState, onLogin: () -> Unit) {
    val context = LocalContext.current
    Column(
        Modifier.fillMaxSize().background(Color(0xFFFEFBF7).takeIf { !isDark() } ?: MaterialTheme.colorScheme.background)
            .safeDrawingPadding().verticalScroll(rememberScrollState()).padding(vertical = 12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
            WelcomeLockup(Modifier.weight(1f), scale = 0.92f)
            LanguageSwitch(state, Modifier.size(width = 120.dp, height = 44.dp))
        }
        Image(
            painterResource(R.drawable.welcome_illustration),
            contentDescription = tr(
                "Comic: Vor dem Arbeitsgericht München packt eine Anwältin in Robe und Flip-Flops die Justitia-Statue am Hals.",
                "Comic: in front of the Munich labour court, a lawyer in a gown and flip-flops grabs the Justitia statue by the neck.",
            ),
            contentScale = ContentScale.FillWidth,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )
        Column(Modifier.padding(horizontal = 24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                buildAnnotatedString {
                    withStyle(SpanStyle(color = MaterialTheme.colorScheme.primary)) { append(tr("Recht verstehen.", "Understand the law.")) }
                    append("\n"); append(tr("Einfach fragen.", "Just ask."))
                },
                style = MaterialTheme.typography.displaySmall.copy(fontWeight = FontWeight.Bold), textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(12.dp))
            Text(
                tr(
                    "Stellen Sie Ihre Rechtsfrage in eigenen Worten – Schimmelpilz antwortet mit den passenden Gesetzen.",
                    "Ask your legal question in your own words – Schimmelpilz answers with the relevant statutes.",
                ),
                style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(24.dp))
            Button(onClick = onLogin, modifier = Modifier.fillMaxWidth().height(56.dp), shape = RoundedCornerShape(50)) {
                Icon(Icons.Outlined.ChatBubbleOutline, null); Spacer(Modifier.size(12.dp))
                Text(tr("Los geht’s", "Get started"), style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.size(12.dp)); Icon(Icons.AutoMirrored.Outlined.ArrowForward, null)
            }
            Spacer(Modifier.height(10.dp))
            FilledTonalButton(onClick = { openWeb(context, "?open=register") }, modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(50)) {
                Icon(Icons.Filled.Person, null); Spacer(Modifier.size(10.dp))
                Text(tr("Neues Konto im Browser erstellen", "Create an account in the browser"))
            }
            Spacer(Modifier.height(12.dp))
            Text(
                tr("Allgemeine Rechtsinformation, keine anwaltliche Beratung im Einzelfall.", "General legal information, not individual legal advice."),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun isDark() = MaterialTheme.colorScheme.background.red < 0.5f

@Composable
fun LoginScreen(state: AppState, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var needsCode by remember { mutableStateOf(false) }
    var show by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val wrong = tr("E-Mail oder Passwort ist nicht korrekt.", "Email or password is incorrect.")
    val badCode = tr("Der Bestätigungscode ist nicht korrekt.", "The verification code is incorrect.")
    val limited = tr("Zu viele Versuche. Bitte in 15 Minuten erneut versuchen.", "Too many attempts. Please try again in 15 minutes.")
    val generic = errorText("")
    val offline = errorText("network")

    fun submit() {
        if (busy) return
        busy = true; error = null
        scope.launch {
            try {
                state.signedIn(state.api.login(email, password, code.takeIf { needsCode }))
            } catch (e: ApiException) {
                when {
                    e.detail == "mfa_required" -> { needsCode = true }
                    e.detail == "mfa_code_invalid" -> error = badCode
                    e.status == 401 -> error = wrong
                    e.status == 429 -> error = limited
                    e.status == 0 -> error = offline
                    else -> error = generic
                }
            } finally { busy = false }
        }
    }

    Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp)) {
        IconButton(onClick = onBack, modifier = Modifier.padding(top = 8.dp)) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, tr("Zurück", "Back")) }
        LoginLockup(Modifier.fillMaxWidth().padding(top = 4.dp))
        Spacer(Modifier.height(16.dp))
        Text(tr("Anmelden", "Sign in"), style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(16.dp))
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedTextField(email, { email = it }, label = { Text(tr("E-Mail", "Email")) }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next), modifier = Modifier.fillMaxWidth())
            OutlinedTextField(password, { password = it }, label = { Text(tr("Passwort", "Password")) }, singleLine = true,
                visualTransformation = if (show) VisualTransformation.None else PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = if (needsCode) ImeAction.Next else ImeAction.Done),
                trailingIcon = {
                    IconButton(onClick = { show = !show }) {
                        Icon(if (show) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility, tr(if (show) "Passwort verbergen" else "Passwort anzeigen", if (show) "Hide password" else "Show password"))
                    }
                },
                modifier = Modifier.fillMaxWidth())
            if (needsCode) {
                Text(tr("Ihr Konto ist mit Zwei-Faktor-Anmeldung geschützt. Code aus der Authenticator-App oder einen Wiederherstellungscode eingeben.",
                    "Your account uses two-factor sign-in. Enter the code from your authenticator app or a recovery code."),
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(code, { code = it.trim() }, label = { Text(tr("Bestätigungscode", "Verification code")) }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done), modifier = Modifier.fillMaxWidth())
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
            Button(onClick = ::submit, enabled = email.isNotBlank() && password.isNotBlank() && (!needsCode || code.isNotBlank()) && !busy,
                modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(50)) {
                if (busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                else Text(tr("Anmelden", "Sign in"), style = MaterialTheme.typography.titleMedium)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                TextButton(onClick = { openWeb(context, "?open=forgot") }) { Text(tr("Passwort vergessen?", "Forgot password?")) }
                TextButton(onClick = { openWeb(context, "?open=register") }) { Text(tr("Registrieren", "Register")) }
            }
            ServerSetting(state)
        }
    }
}

/** Shows which server the app uses and lets the user point it at their own (e.g. a test server in the home network). */
@Composable
private fun ServerSetting(state: AppState) {
    val server by state.server.collectAsState()
    var editing by remember { mutableStateOf(false) }
    var text by remember(server) { mutableStateOf(server.removeSuffix("/")) }
    var invalid by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 24.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Outlined.Dns, null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp))
            Spacer(Modifier.size(8.dp))
            Text(tr("Server: ", "Server: ") + server.removeSuffix("/"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
            TextButton(onClick = { editing = !editing }) { Text(if (editing) tr("Schließen", "Close") else tr("Ändern", "Change")) }
        }
        if (editing) {
            OutlinedTextField(text, { text = it; invalid = false }, label = { Text(tr("Server-Adresse", "Server address")) }, singleLine = true, isError = invalid,
                supportingText = { Text(if (invalid) tr("Keine gültige Adresse.", "Not a valid address.") else tr("z. B. kanzlei.example.de oder 192.168.1.20:8001", "e.g. kanzlei.example.com or 192.168.1.20:8001")) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done), modifier = Modifier.fillMaxWidth())
            FilledTonalButton(onClick = {
                val url = Server.normalize(text)
                if (url == null) invalid = true else { state.setServer(url); editing = false }
            }, modifier = Modifier.align(Alignment.End)) { Text(tr("Übernehmen", "Apply")) }
        }
    }
}
