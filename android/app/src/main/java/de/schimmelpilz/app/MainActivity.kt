package de.schimmelpilz.app

import android.content.Intent
import android.os.Bundle
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import de.schimmelpilz.app.ui.AnimatedSplash
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Folder
import androidx.compose.material.icons.outlined.GridView
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import de.schimmelpilz.app.ui.ProvideLang
import de.schimmelpilz.app.ui.Spark
import de.schimmelpilz.app.ui.screens.AssistantScreen
import de.schimmelpilz.app.ui.screens.CaseDetailScreen
import de.schimmelpilz.app.ui.screens.CasesScreen
import de.schimmelpilz.app.ui.screens.ChatScreen
import de.schimmelpilz.app.ui.screens.DeadlinesScreen
import de.schimmelpilz.app.ui.screens.InboxScreen
import de.schimmelpilz.app.ui.screens.LoginScreen
import de.schimmelpilz.app.ui.screens.MoreScreen
import de.schimmelpilz.app.ui.screens.WelcomeScreen
import de.schimmelpilz.app.ui.theme.SchimmelpilzTheme
import de.schimmelpilz.app.ui.tr
import java.net.URLDecoder
import java.net.URLEncoder

class MainActivity : ComponentActivity() {
    private val state: AppState by viewModels()

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        intent.getStringExtra(Reminders.OPEN_TAB)?.let { state.pendingTab.value = it }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // System start screen first; it hands over to the animated splash on the first frame.
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (savedInstanceState == null) state.pendingTab.value = intent.getStringExtra(Reminders.OPEN_TAB)
        setContent {
            val lang by state.lang.collectAsStateWithLifecycle()
            val mode by state.themeMode.collectAsStateWithLifecycle()
            val dark = when (mode) { ThemeMode.Dark -> true; ThemeMode.Light -> false; ThemeMode.System -> isSystemInDarkTheme() }
            SchimmelpilzTheme(dark = dark) {
                ProvideLang(lang) {
                    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { Root(state) }
                }
            }
        }
    }
}

@Composable
private fun Root(state: AppState) {
    val checked by state.sessionChecked.collectAsStateWithLifecycle()
    val user by state.user.collectAsStateWithLifecycle()
    // Played once per app start (kept across rotation); stays until the stored session has been checked.
    var introPlayed by rememberSaveable { mutableStateOf(false) }
    Crossfade(targetState = introPlayed && checked, animationSpec = tween(450), label = "splash") { ready ->
        when {
            !ready -> AnimatedSplash(waiting = introPlayed && !checked, onFinished = { introPlayed = true })
            user == null -> SignedOut(state)
            else -> SignedIn(state)
        }
    }
}

@Composable
private fun SignedOut(state: AppState) {
    val nav = rememberNavController()
    NavHost(nav, startDestination = "welcome") {
        composable("welcome") { WelcomeScreen(state, onLogin = { nav.navigate("login") }) }
        composable("login") { LoginScreen(state, onBack = { nav.popBackStack() }) }
    }
}

private data class Tab(val route: String, val icon: @Composable () -> Unit, val label: @Composable () -> String)

fun enc(value: String): String = URLEncoder.encode(value, "UTF-8")
private fun dec(value: String?): String = value?.let { URLDecoder.decode(it, "UTF-8") } ?: ""

@Composable
private fun SignedIn(state: AppState) {
    val nav = rememberNavController()
    val inbox by state.inbox.collectAsStateWithLifecycle()
    val open = inbox.count { it.caseId == null }
    val tabs = listOf(
        Tab("assistant", { Spark(size = 20.dp) }, { tr("Assistent", "Assistant") }),
        Tab("cases", { Icon(Icons.Outlined.Folder, null) }, { tr("Akten", "Cases") }),
        Tab("inbox", {
            BadgedBox(badge = { if (open > 0) Badge { Text("$open") } }) { Icon(Icons.Outlined.Inbox, null) }
        }, { tr("Eingang", "Inbox") }),
        Tab("deadlines", { Icon(Icons.Outlined.CalendarMonth, null) }, { tr("Fristen", "Deadlines") }),
        Tab("more", { Icon(Icons.Outlined.GridView, null) }, { tr("Mehr", "More") }),
    )
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route
    val showBar = tabs.any { it.route == route } || route?.startsWith("case/") == true
    val pendingTab by state.pendingTab.collectAsStateWithLifecycle()
    LaunchedEffect(pendingTab) { pendingTab?.let { tab -> if (tabs.any { it.route == tab }) nav.goTab(tab); state.pendingTab.value = null } }
    Scaffold(
        bottomBar = {
            if (showBar) NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                tabs.forEach { tab ->
                    val selected = route == tab.route || (tab.route == "cases" && route?.startsWith("case/") == true)
                    NavigationBarItem(
                        selected = selected,
                        onClick = { nav.goTab(tab.route) },
                        icon = tab.icon,
                        label = { Text(tab.label()) },
                        colors = NavigationBarItemDefaults.colors(
                            indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                            selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                            selectedTextColor = MaterialTheme.colorScheme.primary,
                        ),
                    )
                }
            }
        },
    ) { padding ->
        NavHost(nav, startDestination = "assistant", modifier = Modifier.padding(padding)) {
            composable("assistant") {
                AssistantScreen(state, onAsk = { caseId, question -> nav.navigate("chat/$caseId?q=${enc(question)}") }, onOpenChat = { nav.navigate("chat/$it") }, onOpenDeadlines = { nav.goTab("deadlines") }, onOpenMore = { nav.goTab("more") })
            }
            composable("cases") { CasesScreen(state, onOpen = { nav.navigate("case/$it") }, onOpenDeadlines = { nav.goTab("deadlines") }) }
            composable("case/{id}", listOf(navArgument("id") { type = NavType.StringType })) { back ->
                CaseDetailScreen(state, back.arguments?.getString("id")!!, onBack = { nav.popBackStack() }, onAsk = { nav.navigate("chat/$it") })
            }
            composable("chat/{caseId}?q={q}", listOf(navArgument("caseId") { type = NavType.StringType }, navArgument("q") { type = NavType.StringType; defaultValue = "" })) { back ->
                ChatScreen(state, back.arguments?.getString("caseId")!!, dec(back.arguments?.getString("q")), onBack = { nav.popBackStack() }, onOpenCase = { nav.navigate("case/$it") })
            }
            composable("inbox") { InboxScreen(state) }
            composable("deadlines") { DeadlinesScreen(state, onOpenCase = { nav.navigate("case/$it") }) }
            composable("more") { MoreScreen(state) }
        }
    }
}

private fun NavHostController.goTab(route: String) = navigate(route) {
    popUpTo(graph.findStartDestination().id) { saveState = true }
    launchSingleTop = true
    restoreState = true
}
