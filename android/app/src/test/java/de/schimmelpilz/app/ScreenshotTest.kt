package de.schimmelpilz.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.compose.ui.platform.ViewRootForTest
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasScrollToNodeAction
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeUp
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isRoot
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onLast
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * Walks through the real app against a live server and saves one PNG per screen.
 * Skipped in normal test runs; see android/README.md for how to run it.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w392dp-h850dp-xxhdpi")
class ScreenshotTest {
    @get:Rule val rule = createEmptyComposeRule()
    private val folder = System.getProperty("schimmelpilz.screenshots")

    private lateinit var activity: MainActivity

    /** Draws the activity window, then the topmost dialog or sheet window at its screen position (Robolectric has no frame capture). */
    private fun shot(name: String) {
        rule.waitForIdle()
        val base = activity.window.decorView
        val bitmap = Bitmap.createBitmap(base.width, base.height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        base.draw(canvas)
        val top = (rule.onAllNodes(isRoot()).onLast().fetchSemanticsNode().root as ViewRootForTest).view.rootView
        if (top !== base) {
            if (top.width < base.width || top.height < base.height) canvas.drawColor(0x66000000)
            val at = IntArray(2).also { top.getLocationOnScreen(it) }
            canvas.save(); canvas.translate(at[0].toFloat(), at[1].toFloat()); top.draw(canvas); canvas.restore()
        }
        File(folder!!, "$name.png").parentFile!!.mkdirs()
        File(folder, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private fun waitFor(text: String, substring: Boolean = false) =
        rule.waitUntil(20_000) { rule.onAllNodesWithText(text, substring = substring).fetchSemanticsNodes().isNotEmpty() }

    private fun tap(text: String, substring: Boolean = false) =
        rule.onAllNodes(hasText(text, substring = substring) and hasClickAction())[0].performClick()

    @Test fun walkThroughApp() {
        assumeTrue("Set -Pscreenshots=<folder> to record screenshots", folder != null)
        val context = ApplicationProvider.getApplicationContext<Context>()
        context.getSharedPreferences("schimmelpilz", Context.MODE_PRIVATE).edit().putString("lang", "de").putString("theme", "Light").commit()
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity = it }
            // Frames of the animated splash: paused clock, stepped by hand.
            rule.mainClock.autoAdvance = false
            repeat(34) { frame -> rule.mainClock.advanceTimeBy(90); shot("splash/frame-%02d".format(frame)) }
            rule.mainClock.autoAdvance = true
            waitFor("Recht verstehen.", substring = true)
            shot("01-willkommen")
            tap("Los geht’s")
            waitFor("E-Mail")
            rule.onAllNodesWithText("E-Mail")[0].performTextInput(System.getProperty("schimmelpilz.demo.email") ?: "kanzlei@example.invalid")
            rule.onAllNodesWithText("Passwort")[0].performTextInput(System.getProperty("schimmelpilz.demo.password") ?: "Synthetic-demo-pass-2026!")
            shot("02-anmelden")
            tap("Anmelden")
            waitFor("Hallo, ", substring = true)
            waitFor("Nächste Frist", substring = true)
            shot("03-assistent")

            tap("Akten")
            waitFor("Mietminderung Heizungsausfall")
            shot("04-akten")
            tap("Mietminderung Heizungsausfall")
            waitFor("Frage zu dieser Akte")
            shot("05-akte")

            tap("Frage zu dieser Akte")
            waitFor("Nächste Schritte", substring = true)
            shot("06-antwort")
            repeat(2) { _ -> rule.onAllNodes(hasScrollToNodeAction())[0].performTouchInput { swipeUp() } }
            shot("06b-antwort-quellen")
            tap("§ 536 BGB")
            waitFor("Wortlaut aus der amtlichen Quelle", substring = true)
            shot("07-quelle")
            repeat(2) { _ -> scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }; rule.waitForIdle() }

            tap("Eingang")
            waitFor("Brief scannen")
            shot("08-posteingang")
            tap("Fristen")
            waitFor("NÄCHSTE 10 TAGE")
            shot("09-fristen")
            // Dialogs with text fields never go idle under Robolectric, so the task dialog is not recorded.

            tap("Mehr")
            waitFor("Kostenloser Pilotzugang", substring = true)
            shot("11-mehr")
            rule.onAllNodes(hasText("Dunkel") and hasClickAction())[0].performScrollTo().performClick()
            tap("Assistent")
            waitFor("Hallo, ", substring = true)
            shot("12-assistent-dunkel")
        }
    }
}
