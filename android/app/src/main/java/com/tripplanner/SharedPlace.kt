package com.tripplanner

import java.net.URI
import java.net.URLDecoder

/** Extract only explicit destination coordinates. Short links and camera positions
 * stay unresolved until a place service or the user confirms the destination.
 */
internal fun sharedCoordinates(text: String?): Pair<Double, Double>? {
    if (text.isNullOrBlank()) return null
    fun parse(value: String): Pair<Double, Double>? {
        val parts = value.removePrefix("loc:").split(',').map { it.trim().toDoubleOrNull() }
        if (parts.size != 2) return null
        val latitude = parts[0] ?: return null
        val longitude = parts[1] ?: return null
        return if (latitude.isFinite() && longitude.isFinite() && latitude in -90.0..90.0 && longitude in -180.0..180.0) latitude to longitude else null
    }
    parse(text.trim())?.let { return it }
    val link = Regex("https?://[^\\s]+").find(text)?.value ?: return null
    return runCatching {
        val uri = URI(link)
        val parameters = uri.rawQuery.orEmpty().split('&').mapNotNull { parameter ->
            val parts = parameter.split('=', limit = 2)
            if (parts.size == 2) URLDecoder.decode(parts[0], "UTF-8") to URLDecoder.decode(parts[1], "UTF-8") else null
        }.toMap()
        listOf("ll", "q", "query").firstNotNullOfOrNull { key -> parameters[key]?.let(::parse) }
    }.getOrNull()
}
