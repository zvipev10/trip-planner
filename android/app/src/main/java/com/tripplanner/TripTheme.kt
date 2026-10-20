package com.tripplanner

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

internal val WebInk = Color(0xFF173B32)
internal val WebPaper = Color(0xFFF7F6F0)
internal val WebLime = Color(0xFFE5EDBD)

@Composable
internal fun TripTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Color(0xFF24604C), onPrimary = Color.White,
            primaryContainer = WebLime, onPrimaryContainer = WebInk,
            secondary = Color(0xFF69756E), onSecondary = Color.White,
            background = WebPaper, onBackground = WebInk,
            surface = Color.White, onSurface = WebInk,
            surfaceVariant = Color(0xFFEDF1E7), onSurfaceVariant = Color(0xFF69756E),
            surfaceContainer = WebPaper, surfaceContainerHigh = WebPaper, surfaceContainerHighest = Color.White,
            outline = Color(0xFFCBD1C6), outlineVariant = Color(0xFFDEDFD4),
            error = Color(0xFF9E3432), onError = Color.White,
        ),
        shapes = Shapes(small = RoundedCornerShape(11.dp), medium = RoundedCornerShape(16.dp), large = RoundedCornerShape(20.dp)),
        typography = Typography(
            headlineLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 32.sp, lineHeight = 36.sp, letterSpacing = (-1).sp),
            headlineSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 24.sp, lineHeight = 29.sp),
            titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 22.sp),
            titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 17.sp, lineHeight = 23.sp),
            labelSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 10.sp, letterSpacing = 1.5.sp),
        ),
        content = content,
    )
}

@Composable
internal fun BrandMark() {
    Box(Modifier.size(42.dp).clip(RoundedCornerShape(12.dp)).background(WebInk)) {
        Icon(painterResource(R.drawable.ic_launcher_foreground), contentDescription = null, tint = WebLime, modifier = Modifier.size(42.dp))
    }
}
