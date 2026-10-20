package com.tripplanner

import java.net.URI
import java.net.URLDecoder

/** Extract destination coordinates locally; camera positions stay unresolved. */
internal fun sharedCoordinates(text: String?): Pair<Double, Double>? {
    if (text.isNullOrBlank()) return null
    fun parse(value: String): Pair<Double, Double>? {
        val parts = value.replace(Regex("\\s*\\([^)]*\\)$"), "").removePrefix("loc:").split(',').map { it.trim().toDoubleOrNull() }
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
        val data = Regex("!3d(-?\\d+(?:\\.\\d+)?)!4d(-?\\d+(?:\\.\\d+)?)").find(URLDecoder.decode(link, "UTF-8"))
        if (data != null) parse("${data.groupValues[1]},${data.groupValues[2]}")?.let { return@runCatching it }
        val geohash = Regex("/ul/h([0-9bcdefghjkmnpqrstuvwxyz]{6,12})(?:$|/)").find(uri.path.orEmpty())
        if (uri.host in setOf("waze.com", "www.waze.com", "ul.waze.com") && geohash != null) {
            val bounds = arrayOf(doubleArrayOf(-180.0, 180.0), doubleArrayOf(-90.0, 90.0))
            var axis = 0
            for (char in geohash.groupValues[1]) {
                val value = "0123456789bcdefghjkmnpqrstuvwxyz".indexOf(char)
                for (bit in 4 downTo 0) {
                    val b = bounds[axis]
                    b[if ((value shr bit) and 1 == 1) 0 else 1] = (b[0] + b[1]) / 2
                    axis = 1 - axis
                }
            }
            return@runCatching (bounds[1][0] + bounds[1][1]) / 2 to (bounds[0][0] + bounds[0][1]) / 2
        }
        listOf("destination", "ll", "q", "query").firstNotNullOfOrNull { key -> parameters[key]?.let(::parse) }
    }.getOrNull()
}


internal fun sharedPlaceName(text: String): String? = runCatching {
    val link = Regex("https?://[^\\s]+").find(text) ?: return@runCatching null
    val uri = URI(link.value)
    val pathName = Regex("/maps/place/([^/]+)").find(uri.rawPath.orEmpty())?.groupValues?.get(1)
        ?.let { URLDecoder.decode(it, "UTF-8") }
    if (!pathName.isNullOrBlank() && !pathName.matches(Regex("[-\\d., +]+"))) return@runCatching pathName.take(200)
    val query = uri.rawQuery.orEmpty().split('&').mapNotNull {
        val pair = it.split('=', limit = 2)
        if (pair.size == 2) URLDecoder.decode(pair[0], "UTF-8") to URLDecoder.decode(pair[1], "UTF-8") else null
    }.toMap()
    for (key in listOf("name", "venue_name", "q", "query")) {
        val value = query[key]
        if (!value.isNullOrBlank() && sharedCoordinates(value) == null && !value.startsWith("place_id:")) return@runCatching value.take(200)
    }
    text.substring(0, link.range.first).trim().trimEnd(':', '-', '–').trim().takeIf { it.isNotBlank() }?.take(200)
}.getOrNull()
