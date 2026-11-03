package de.schimmelpilz.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import de.schimmelpilz.app.R

// Brand colours from the web app (green #075442, dark green #043c30, gold #987243).
val Green = Color(0xFF075442)
val GreenDark = Color(0xFF043C30)
val Gold = Color(0xFF8A6538)

private val Light = lightColorScheme(
    primary = Green, onPrimary = Color.White,
    primaryContainer = Color(0xFFDCEBE2), onPrimaryContainer = GreenDark,
    secondary = Gold, onSecondary = Color.White,
    secondaryContainer = Color(0xFFDCEBE2), onSecondaryContainer = GreenDark,
    tertiary = Color(0xFF8A3B12),
    background = Color.White, onBackground = Color(0xFF1B1F1E),
    surface = Color.White, onSurface = Color(0xFF1B1F1E),
    surfaceVariant = Color(0xFFF1F4F1), onSurfaceVariant = Color(0xFF4F5957),
    surfaceContainer = Color(0xFFF1F4F1), surfaceContainerHigh = Color(0xFFEAEFEB),
    outline = Color(0xFFD5DBD7), outlineVariant = Color(0xFFE3E7E4),
    error = Color(0xFFB3261E),
)

private val Dark = darkColorScheme(
    primary = Color(0xFF8FDCB4), onPrimary = Color(0xFF0B2A20),
    primaryContainer = Color(0xFF1F4A3B), onPrimaryContainer = Color(0xFFCDEBDC),
    secondary = Color(0xFFE0B77A), onSecondary = Color(0xFF3B2A10),
    secondaryContainer = Color(0xFF1F4A3B), onSecondaryContainer = Color(0xFFCDEBDC),
    tertiary = Color(0xFFF2B08C),
    background = Color(0xFF131314), onBackground = Color(0xFFE6E8E7),
    surface = Color(0xFF131314), onSurface = Color(0xFFE6E8E7),
    surfaceVariant = Color(0xFF1E1F20), onSurfaceVariant = Color(0xFFA7AFAD),
    surfaceContainer = Color(0xFF1E1F20), surfaceContainerHigh = Color(0xFF282A2B),
    outline = Color(0xFF3A3D3C), outlineVariant = Color(0xFF2C2F2E),
    error = Color(0xFFF2B8B5),
)

@OptIn(androidx.compose.ui.text.ExperimentalTextApi::class)
private fun jakarta(weight: Int) = Font(
    R.font.plus_jakarta_sans, FontWeight(weight),
    variationSettings = FontVariation.Settings(FontVariation.weight(weight)),
)

val Jakarta = FontFamily(jakarta(400), jakarta(500), jakarta(600), jakarta(700), jakarta(800))

private val base = Typography()
private fun TextStyle.j() = copy(fontFamily = Jakarta)

val AppTypography = Typography(
    displaySmall = base.displaySmall.j().copy(fontWeight = FontWeight.SemiBold, fontSize = 38.sp, lineHeight = 46.sp, letterSpacing = (-0.6).sp),
    headlineMedium = base.headlineMedium.j().copy(fontWeight = FontWeight.Bold, fontSize = 28.sp, lineHeight = 34.sp),
    headlineSmall = base.headlineSmall.j().copy(fontWeight = FontWeight.Bold, fontSize = 24.sp, lineHeight = 30.sp),
    titleLarge = base.titleLarge.j().copy(fontWeight = FontWeight.SemiBold),
    titleMedium = base.titleMedium.j().copy(fontWeight = FontWeight.Bold),
    titleSmall = base.titleSmall.j().copy(fontWeight = FontWeight.SemiBold),
    bodyLarge = base.bodyLarge.j().copy(fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = base.bodyMedium.j(),
    bodySmall = base.bodySmall.j(),
    labelLarge = base.labelLarge.j().copy(fontWeight = FontWeight.SemiBold),
    labelMedium = base.labelMedium.j().copy(fontWeight = FontWeight.SemiBold),
    labelSmall = base.labelSmall.j().copy(fontWeight = FontWeight.Bold),
)

@Immutable
data class BrandColors(val greeting: Brush, val warning: Color, val onWarning: Color)

val LocalBrand = staticCompositionLocalOf {
    BrandColors(Brush.linearGradient(listOf(Green, Gold)), Color(0xFFFBF1DF), Color(0xFF6B4E24))
}

@Composable
fun SchimmelpilzTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val colors: ColorScheme = if (dark) Dark else Light
    val brand = if (dark) {
        BrandColors(Brush.linearGradient(listOf(Color(0xFF7FD3A8), Color(0xFFE0B77A))), Color(0xFF3A2E1C), Color(0xFFF6E2C2))
    } else {
        BrandColors(Brush.linearGradient(listOf(Green, Color(0xFF2E7A5C), Gold)), Color(0xFFFBF1DF), Color(0xFF6B4E24))
    }
    androidx.compose.runtime.CompositionLocalProvider(LocalBrand provides brand) {
        MaterialTheme(colorScheme = colors, typography = AppTypography, content = content)
    }
}
