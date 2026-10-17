package com.tripplanner

import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST
import java.util.concurrent.TimeUnit

data class RoutePoint(val id: String, val latitude: Double, val longitude: Double)
data class RouteRequest(val revision: Long, val start: RoutePoint, val end: RoutePoint, val stops: List<RoutePoint>)
data class RouteResult(val revision: Long?, val orderedStopIds: List<String>?, val distanceMeters: Long?, val legDistancesMeters: List<Long>?, val status: String?)
data class RoutePlan(val tripId: String, val revision: Long, val order: List<String>, val distance: Long?, val manual: Boolean)

fun routeRequest(snapshot: TripSnapshot, manualOrder: List<String>? = null): RouteRequest {
    val trip = snapshot.trip
    val places = snapshot.locations.associateBy { it.id }
    fun point(id: String?, wireId: String? = null): RoutePoint {
        val place = requireNotNull(places[id]) { "Choose both starting and ending points." }
        val lat = place.latitude
        val lon = place.longitude
        require(lat != null && lon != null && lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0) { "Confirm coordinates for ${place.name}." }
        return RoutePoint(wireId ?: place.id, lat, lon)
    }
    val stops = snapshot.locations.filter { it.id != trip.startId && it.id != trip.endId }.sortedWith(compareBy({ it.createdAt }, { it.id })).map { it.id }
    require(stops.size <= 20) { "Use at most 20 intermediate stops." }
    val order = manualOrder ?: stops
    require(order.size == stops.size && order.toSet() == stops.toSet()) { "Locations changed. Optimize again." }
    // Role IDs allow a round trip to use the same saved place at both endpoints.
    return RouteRequest(trip.revision, point(trip.startId, "endpoint:start"), point(trip.endId, "endpoint:end"), order.map { point(it) })
}

fun validateRoute(result: RouteResult, request: RouteRequest, manual: Boolean): RouteResult {
    val order = result.orderedStopIds
    val legs = result.legDistancesMeters
    val expected = request.stops.map { it.id }
    require(result.revision == request.revision && result.status == if (manual) "manual" else "optimized") { "Invalid routing response." }
    require(order != null && order.size == expected.size && order.toSet() == expected.toSet() && (!manual || order == expected)) { "Invalid stop order from server." }
    require(legs != null && legs.size == expected.size + 1 && legs.all { it in 0..1_000_000_000L } && result.distanceMeters == legs.sum()) { "Invalid distance from server." }
    return result
}

interface RouteService {
    @POST("v1/routes/optimize") suspend fun optimize(@Body request: RouteRequest): RouteResult
    @POST("v1/routes/calculate") suspend fun calculate(@Body request: RouteRequest): RouteResult
}

fun routeService(): RouteService {
    require(BuildConfig.API_URL.isNotBlank()) { "A server URL must be configured for this build." }
    val client = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(90, TimeUnit.SECONDS).callTimeout(100, TimeUnit.SECONDS).build()
    return Retrofit.Builder().baseUrl(BuildConfig.API_URL).client(client).addConverterFactory(GsonConverterFactory.create()).build().create(RouteService::class.java)
}
