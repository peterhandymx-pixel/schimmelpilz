package de.schimmelpilz.app.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.keyframes
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import de.schimmelpilz.app.R
import de.schimmelpilz.app.ui.theme.Jakarta
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val Cream = Color(0xFFFEFBF7)
private val Ink = Color(0xFF101B1D)
private val Green = Color(0xFF075442)
private val Gold = Color(0xFFB8862F)
private val Muted = Color(0xFF4A5559)

/**
 * Animated start screen, continuing the system splash (same cream background and badge): the badge bounces in and
 * shakes like the scene in it, the name slides up, the gold § rule draws out, the claim and the slogan fade in. [onFinished] fires once
 * the animation has played (~3 s); while the app is still checking the session afterwards, a thin progress bar shows.
 */
@Composable
fun AnimatedSplash(waiting: Boolean, onFinished: () -> Unit) {
    val badge = remember { Animatable(0f) }
    val shake = remember { Animatable(0f) }
    val name = remember { Animatable(0f) }
    val rule = remember { Animatable(0f) }
    val claim = remember { Animatable(0f) }
    val slogan = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        badge.animateTo(1f, spring(dampingRatio = 0.42f, stiffness = Spring.StiffnessLow))
        launch {
            shake.animateTo(0f, keyframes {
                durationMillis = 520
                -7f at 70; 6f at 150; -5f at 230; 3f at 320; -1.5f at 410; 0f at 520
            })
        }
        name.animateTo(1f, tween(380, easing = FastOutSlowInEasing))
        rule.animateTo(1f, tween(360, easing = FastOutSlowInEasing))
        claim.animateTo(1f, tween(280))
        slogan.animateTo(1f, tween(520, easing = FastOutSlowInEasing))
        delay(1300) // long enough to read the slogan before the app fades in
        onFinished()
    }
    val claimText = brandClaim()
    val sloganText = tr("Findet Klarheit und die Wahrheit",
        "Find clarity and the truth")
    Box(Modifier.fillMaxSize().background(Cream).semantics { contentDescription = "$BRAND – $claimText. $sloganText" }, contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(horizontal = 32.dp)) {
            Image(
                painterResource(R.drawable.login_logo), contentDescription = null,
                modifier = Modifier.height(190.dp).graphicsLayer {
                    // Starts at the size of the system splash icon, then overshoots to full size.
                    val scale = 0.48f + 0.52f * badge.value
                    scaleX = scale; scaleY = scale; rotationZ = shake.value
                    alpha = (badge.value * 3f).coerceIn(0f, 1f)
                },
            )
            Spacer(Modifier.height(18.dp))
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.graphicsLayer { alpha = name.value; translationY = (1f - name.value) * 28.dp.toPx() },
            ) {
                Text("Rechtsassistentin", style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.ExtraBold, fontSize = 24.sp, letterSpacing = (-0.01).em), color = Ink)
                Text("Schimmelpilz", style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.ExtraBold, fontSize = 38.sp, letterSpacing = (-0.02).em, lineHeight = 42.sp), color = Green)
            }
            Spacer(Modifier.height(10.dp))
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
                Box(Modifier.width((96 * rule.value).dp).height(2.dp).background(Gold))
                Text("§", modifier = Modifier.padding(horizontal = 10.dp).alpha(rule.value), style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.Bold, fontSize = 22.sp), color = Gold)
                Box(Modifier.width((96 * rule.value).dp).height(2.dp).background(Gold))
            }
            Spacer(Modifier.height(10.dp))
            Text(claimText, modifier = Modifier.alpha(claim.value), textAlign = TextAlign.Center,
                style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.Medium, fontSize = 13.sp, lineHeight = 17.sp), color = Muted)
            Spacer(Modifier.height(22.dp))
            Text(sloganText, textAlign = TextAlign.Center,
                modifier = Modifier.widthIn(max = 320.dp).graphicsLayer { alpha = slogan.value; translationY = (1f - slogan.value) * 16.dp.toPx() },
                style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.SemiBold, fontSize = 17.sp, lineHeight = 24.sp, letterSpacing = (-0.005).em), color = Ink)
            Spacer(Modifier.height(24.dp))
            Box(Modifier.height(3.dp).width(120.dp)) {
                if (waiting) LinearProgressIndicator(Modifier.fillMaxSize(), color = Green, trackColor = Green.copy(alpha = 0.12f))
            }
        }
    }
}
