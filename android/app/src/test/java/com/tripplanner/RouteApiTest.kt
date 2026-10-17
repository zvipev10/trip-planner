package com.tripplanner

import org.junit.Assert.*
import org.junit.Test

class RouteApiTest {
    private val places = listOf("home", "a", "b").map { TripLocation(it, "trip", it, "", 32.0, 34.0, createdAt = 0) }
    private val snapshot = TripSnapshot(Trip("trip", "Test", revision = 5, startId = "home", endId = "home"), places)

    @Test fun roundTripHasUniqueEndpointRoles() {
        val request = routeRequest(snapshot)
        assertNotEquals(request.start.id, request.end.id)
        assertEquals(request.start.latitude, request.end.latitude, 0.0)
        assertEquals(listOf("a", "b"), request.stops.map { it.id })
    }
    @Test fun differentEndpointsAreExcludedFromStops() {
        val request = routeRequest(snapshot.copy(trip = snapshot.trip.copy(endId = "b")))
        assertEquals(listOf("a"), request.stops.map { it.id })
        assertEquals(34.0, request.end.longitude, 0.0)
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsMissingEndpoints() {
        routeRequest(snapshot.copy(trip = snapshot.trip.copy(startId = null)))
    }
    @Test fun manualOrderIsPreserved() {
        assertEquals(listOf("b", "a"), routeRequest(snapshot, listOf("b", "a")).stops.map { it.id })
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsStaleManualOrder() { routeRequest(snapshot, listOf("a", "a")) }
    @Test(expected = IllegalArgumentException::class) fun rejectsMissingCoordinates() {
        routeRequest(snapshot.copy(locations = places.map { it.copy(latitude = null) }))
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsTooManyStops() {
        routeRequest(snapshot.copy(locations = places + (1..21).map { places[1].copy(id = "extra$it") }))
    }
    @Test fun acceptsMatchingResponse() {
        val result = RouteResult(5, listOf("b", "a"), 30, listOf(10, 10, 10), "optimized")
        assertEquals(result, validateRoute(result, routeRequest(snapshot), false))
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsStaleRevision() {
        validateRoute(RouteResult(4, listOf("b", "a"), 30, listOf(10, 10, 10), "optimized"), routeRequest(snapshot), false)
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsIncorrectDistance() {
        validateRoute(RouteResult(5, listOf("b", "a"), 31, listOf(10, 10, 10), "optimized"), routeRequest(snapshot), false)
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsManualServerReordering() {
        validateRoute(RouteResult(5, listOf("b", "a"), 30, listOf(10, 10, 10), "manual"), routeRequest(snapshot), true)
    }
}
