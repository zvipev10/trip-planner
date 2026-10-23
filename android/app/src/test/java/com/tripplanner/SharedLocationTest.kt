package com.tripplanner

import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class SharedLocationTest {
    @Test fun choosingTripPreparesResolvedPlaceWithoutReview() = runBlocking {
        val source="https://maps.app.goo.gl/example"
        val place=sharedLocation(source,"chosen-trip",5,"import-id") { PlaceResolveResult("Cafe",32.08,34.78) }
        assertEquals("chosen-trip",place.tripId)
        assertEquals("import-id",place.id)
        assertEquals("Cafe",place.name)
        assertEquals(source,place.source)
        assertEquals(32.08,place.latitude!!,0.0)
    }
    @Test fun coordinateShareHasGeneratedNameAndNoRemoteCall() = runBlocking {
        val place=sharedLocation("32.08,34.78","trip",5,"import-id") { error("Remote not needed") }
        assertEquals("Place 5",place.name)
        assertTrue(place.resolved)
    }
    @Test fun remoteFailureDoesNotProduceSavedPlace() = runBlocking {
        var failed=false
        try {sharedLocation("https://maps.app.goo.gl/bad","trip",1,"id") {throw java.io.IOException("offline")}}
        catch (_:java.io.IOException) {failed=true}
        assertTrue(failed)
    }
}
