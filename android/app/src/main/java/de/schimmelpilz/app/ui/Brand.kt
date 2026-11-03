package de.schimmelpilz.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import de.schimmelpilz.app.R
import de.schimmelpilz.app.ui.theme.Jakarta

const val BRAND = "Rechtsassistentin Schimmelpilz"

@Composable
fun brandClaim() = tr("Entwickelt von einem ausgebildeten Rechtsanwaltsfachangestellten", "Developed by a trained German paralegal")

@Composable
fun BrandMark(height: Dp, modifier: Modifier = Modifier) =
    Image(painterResource(R.drawable.logo_mark), contentDescription = null, modifier = modifier.height(height))

/**
 * CI logo. Full: the supplied artwork with name and claim (light backgrounds); its black lettering would vanish on dark
 * backgrounds, so dark mode and [compact] use the artwork plus live text. [scale] 1 = 64 dp artwork in the text variant.
 */
@Composable
fun BrandLockup(modifier: Modifier = Modifier, compact: Boolean = false, scale: Float = 1f, fullWidth: Dp = 300.dp) {
    val claim = brandClaim()
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    if (!compact && !dark) {
        Image(painterResource(R.drawable.logo_full), contentDescription = "$BRAND – $claim", modifier = modifier.widthIn(max = fullWidth).fillMaxWidth())
        return
    }
    Row(
        modifier.clearAndSetSemantics { contentDescription = if (compact) BRAND else "$BRAND – $claim" },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy((8 * scale).dp),
    ) {
        BrandMark(((if (compact) 46 else 64) * scale).dp)
        Column {
            Text("Rechtsassistentin", style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.ExtraBold, fontSize = (16 * scale).sp, letterSpacing = (-0.01).em, lineHeight = (19 * scale).sp), color = MaterialTheme.colorScheme.onSurface)
            Text("Schimmelpilz", style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.ExtraBold, fontSize = (23 * scale).sp, letterSpacing = (-0.02).em, lineHeight = (26 * scale).sp), color = MaterialTheme.colorScheme.primary)
            if (!compact) Text(claim, style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.Medium, fontSize = (10.5 * scale).sp, lineHeight = (13 * scale).sp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** Entry-screen header from the original design: portrait badge with name and claim as live text. */
@Composable
fun WelcomeLockup(modifier: Modifier = Modifier, scale: Float = 1f) {
    val claim = brandClaim()
    Row(
        modifier.clearAndSetSemantics { contentDescription = "$BRAND – $claim" },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy((10 * scale).dp),
    ) {
        Image(painterResource(R.drawable.welcome_badge), contentDescription = null, modifier = Modifier.size((64 * scale).dp))
        Column {
            Text("Rechtsassistentin", style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.Bold, fontSize = (17 * scale).sp, letterSpacing = (-0.01).em, lineHeight = (20 * scale).sp), color = MaterialTheme.colorScheme.onSurface)
            Text("Schimmelpilz", style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.ExtraBold, fontSize = (24 * scale).sp, letterSpacing = (-0.02).em, lineHeight = (27 * scale).sp), color = MaterialTheme.colorScheme.primary)
            Text(claim, style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.Medium, fontSize = (10.5 * scale).sp, lineHeight = (13 * scale).sp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** Sign-in header: the comic badge with name and claim centred below it. */
@Composable
fun LoginLockup(modifier: Modifier = Modifier) {
    val claim = brandClaim()
    Column(modifier.clearAndSetSemantics { contentDescription = "$BRAND – $claim" }, horizontalAlignment = Alignment.CenterHorizontally) {
        Image(painterResource(R.drawable.login_logo), contentDescription = null, modifier = Modifier.height(150.dp))
        Text("Rechtsassistentin", style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.ExtraBold, fontSize = 20.sp, letterSpacing = (-0.01).em, lineHeight = 24.sp), color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.padding(top = 8.dp))
        Text("Schimmelpilz", style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.ExtraBold, fontSize = 30.sp, letterSpacing = (-0.02).em, lineHeight = 33.sp), color = MaterialTheme.colorScheme.primary)
        Text(claim, style = TextStyle(fontFamily = Jakarta, fontWeight = FontWeight.Medium, fontSize = 12.sp, lineHeight = 15.sp, textAlign = TextAlign.Center), color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp))
    }
}
