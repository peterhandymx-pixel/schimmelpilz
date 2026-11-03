package de.schimmelpilz.app

import android.app.Application
import android.content.Context
import androidx.core.content.edit
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.Configuration
import de.schimmelpilz.app.data.Api
import de.schimmelpilz.app.data.ApiException
import de.schimmelpilz.app.data.CaseFile
import de.schimmelpilz.app.data.InboxItem
import de.schimmelpilz.app.data.SessionCookieJar
import de.schimmelpilz.app.data.User
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import java.util.Locale

/** Provides WorkManager's configuration so it also starts on demand (deadline reminders), e.g. in tests. */
class SchimmelpilzApp : Application(), Configuration.Provider {
    override val workManagerConfiguration: Configuration get() = Configuration.Builder().build()
}

/** The Schimmelpilz server the app talks to: chosen on the sign-in screen, else the build default. */
object Server {
    private val local = Regex("""^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.)""")

    fun url(context: Context): String =
        context.getSharedPreferences("schimmelpilz", Context.MODE_PRIVATE).getString("server", null) ?: BuildConfig.API_BASE_URL

    /** "192.168.1.20:8001" → "http://192.168.1.20:8001/", "kanzlei.de" → "https://kanzlei.de/"; null if not a web address. */
    fun normalize(input: String): String? {
        val text = input.trim().trimEnd('/')
        if (text.isEmpty()) return null
        val withScheme = if ("://" in text) text else (if (local.containsMatchIn(text)) "http://" else "https://") + text
        val url = withScheme.toHttpUrlOrNull() ?: return null
        return url.newBuilder().encodedPath("/").query(null).fragment(null).build().toString()
    }
}

enum class ThemeMode { System, Light, Dark }

/** App-wide state: session, language, theme and the cached case/inbox lists every tab shares. */
class AppState(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("schimmelpilz", Context.MODE_PRIVATE)
    private val cookies = SessionCookieJar(app.getSharedPreferences("session", Context.MODE_PRIVATE))
    val server = MutableStateFlow(Server.url(app))
    var api = Api(server.value, cookies)
        private set

    val lang = MutableStateFlow(prefs.getString("lang", null) ?: if (Locale.getDefault().language == "de") "de" else "en")
    val themeMode = MutableStateFlow(runCatching { ThemeMode.valueOf(prefs.getString("theme", "Light")!!) }.getOrDefault(ThemeMode.Light))

    private val _user = MutableStateFlow<User?>(null)
    val user: StateFlow<User?> = _user
    /** null while the stored session is being checked at start-up. */
    val sessionChecked = MutableStateFlow(false)

    val cases = MutableStateFlow<List<CaseFile>>(emptyList())
    val inbox = MutableStateFlow<List<InboxItem>>(emptyList())
    val loadError = MutableStateFlow<String?>(null)
    /** A tab to open next, e.g. "deadlines" after tapping a reminder. */
    val pendingTab = MutableStateFlow<String?>(null)

    init {
        viewModelScope.launch {
            _user.value = runCatching { api.me() }.getOrNull()
            sessionChecked.value = true
            Reminders.schedule(app, signedIn = _user.value != null)
            if (_user.value != null) refresh()
        }
    }

    /** Switches to another server; the old session cannot be valid there, so it is dropped. */
    fun setServer(url: String) {
        if (url == server.value) return
        cookies.clear()
        prefs.edit { putString("server", url) }
        server.value = url
        api = Api(url, cookies)
        _user.value = null
    }

    fun setLang(value: String) { lang.value = value; prefs.edit { putString("lang", value) } }
    fun setTheme(value: ThemeMode) { themeMode.value = value; prefs.edit { putString("theme", value.name) } }

    fun signedIn(user: User) { _user.value = user; Reminders.schedule(getApplication(), signedIn = true); refresh() }

    /** After the server deleted the account: forget everything locally, back to the welcome screen. */
    fun accountDeleted() { Reminders.schedule(getApplication(), signedIn = false); _user.value = null; cases.value = emptyList(); inbox.value = emptyList() }

    fun signOut() = viewModelScope.launch {
        api.logout(); Reminders.schedule(getApplication(), signedIn = false); _user.value = null; cases.value = emptyList(); inbox.value = emptyList()
    }

    fun refresh() = viewModelScope.launch {
        try {
            cases.value = api.cases().filter { it.archivedAt == null }
            inbox.value = api.inbox()
            loadError.value = null
        } catch (error: ApiException) {
            if (error.status == 401) _user.value = null else loadError.value = error.detail
        }
    }
}
