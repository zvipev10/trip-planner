package com.tripplanner

import com.google.gson.Gson
import org.junit.Assert.*
import org.junit.Test

class SavedArrivalTest {
    private val home = TripLocation("home", "trip", "Home", "", 32.0, 35.0)
    private val stop = TripLocation("stop", "trip", "Stop", "", 32.01, 35.01)
    private val trip = Trip("trip", "Day", revision = 4, startId = "home", endId = "home")
    private val snapshot = TripSnapshot(trip, listOf(home, stop))
    @Test fun arrivalOverrideAppliesToBothRoundTripRoles() {
        val adjusted = home.copy(arrivalLatitude = 32.001, arrivalLongitude = 35.001)
        val request = routeRequest(snapshot.copy(locations = listOf(adjusted, stop)))
        assertEquals(32.0, adjusted.latitude!!, 0.0)
        assertEquals(32.001, request.start.latitude, 0.0)
        assertEquals(request.start.latitude, request.end.latitude, 0.0)
        assertNotEquals(request.start.id, request.end.id)
        assertEquals(32.0, routeRequest(snapshot).start.latitude, 0.0)
    }
    @Test fun savedRouteRestoresOnlyForMatchingRevisionAndStops() {
        val plan = RoutePlan("trip", 4, listOf("stop"), 300, false, listOf(listOf(35.0,32.0),listOf(35.01,32.01),listOf(35.0,32.0)))
        val json = Gson().toJson(plan)
        assertEquals(plan, restoredPlan(json,snapshot))
        assertNull(restoredPlan(json,snapshot.copy(trip=trip.copy(revision=5))))
        assertNull(restoredPlan(Gson().toJson(plan.copy(order=listOf("unknown"))),snapshot))
        assertNull(restoredPlan("not json",snapshot))
        assertNull(restoredPlan(Gson().toJson(plan.copy(geometry=null)),snapshot))
    }
}
