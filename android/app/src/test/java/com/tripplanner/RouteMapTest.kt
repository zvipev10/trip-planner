package com.tripplanner

import org.junit.Assert.*
import org.junit.Test

class RouteMapTest {
    private val trip = Trip("trip", "Map", revision = 7, startId = "home", endId = "end")
    private val locations = listOf("home", "a", "b", "end").map { TripLocation(it, "trip", it, "", 32.0, 34.0) }
    private val line = listOf(listOf(34.78, 32.08), listOf(34.8, 32.1))
    private val plan = RoutePlan("trip", 7, listOf("b", "a"), 1000, false, line)

    @Test fun geometryKeepsGeoJsonLongitudeLatitudeOrder() {
        assertEquals(line, validatedGeometry(RouteGeometry("LineString", line)))
        val payload = mapPayload(trip, locations, plan)
        assertEquals(line, payload.plan.geometry)
        assertEquals(listOf("b", "a"), payload.plan.order)
        assertEquals("home", payload.startId)
        assertEquals("end", payload.endId)
    }
    @Test fun invalidGeometryIsNeverDrawn() {
        assertNull(validatedGeometry(RouteGeometry("Point", line)))
        assertNull(validatedGeometry(RouteGeometry("LineString", listOf(listOf(181.0, 32.0), line[0]))))
        assertNull(validatedGeometry(RouteGeometry("LineString", listOf(listOf(34.0, Double.NaN), line[0]))))
        assertNull(validatedGeometry(RouteGeometry("LineString", listOf(line[0]))))
    }
    @Test fun roundTripRetainsSharedEndpoint() {
        val payload = mapPayload(trip.copy(endId = "home"), locations, plan)
        assertEquals(payload.startId, payload.endId)
    }
    @Test(expected = IllegalArgumentException::class) fun staleRevisionCannotRender() {
        mapPayload(trip.copy(revision = 8), locations, plan)
    }
    @Test(expected = IllegalArgumentException::class) fun staleManualOrderCannotRender() {
        mapPayload(trip, locations, plan.copy(distance = null, geometry = null))
    }
}
