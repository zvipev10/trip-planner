package com.tripplanner

import java.io.IOException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.yield
import org.junit.Assert.*
import org.junit.Test

class PlaceImportTest {
    private val reply = PlaceResolveResult("קרית אריה", 32.0935124, 34.8482224)
    private val short = "https://maps.app.goo.gl/SZuQY5qwP4PJ8woF8?g_st=ic"

    @Test fun localLinksNeedNoBackend() = runBlocking {
        val result = importPlace("https://google.com/maps/place/Cafe+Five/@31,35,15z/data=!3d32.08!4d34.78") { error("No request expected") }
        assertEquals("Cafe Five", result?.name)
        assertEquals(32.08, result!!.latitude!!, 0.0)
        assertEquals(34.78, result.longitude!!, 0.0)
    }
    @Test fun wazeGeohashAndDestinationQuery() {
        val hash = sharedCoordinates("https://waze.com/ul/hsv8wrqkp9")!!
        assertTrue(hash.first in 29.0..34.0 && hash.second in 34.0..36.0)
        assertEquals(32.08 to 34.78, sharedCoordinates("https://google.com/maps/dir/?api=1&destination=32.08%2C34.78"))
    }
    @Test fun explicitNamesAndLabels() {
        assertEquals("Coffee Shop", sharedPlaceName("https://maps.google.com/?q=Coffee+Shop"))
        assertEquals("Cafe", sharedPlaceName("Cafe\nhttps://maps.app.goo.gl/test"))
        assertNull(sharedPlaceName("https://waze.com/ul?ll=32,34"))
    }
    @Test fun automaticResolutionPreservesTypedName() = runBlocking {
        val importer = PlaceImport(this, "Place 5", PlaceDraft("Place 5", ""), { reply }, 0)
        importer.address(short)
        importer.name("My label")
        yield()
        assertEquals("My label", importer.state.value.name)
        assertEquals(reply.latitude.toString(), importer.state.value.latitude)
    }
    @Test fun immediateSaveWaitsForShortLinkAndFillsName() = runBlocking {
        val importer = PlaceImport(this, "Place 5", PlaceDraft("", ""), { reply }, 300)
        var saved: PlaceDraft? = null
        importer.address(short)
        importer.save { saved = it }
        yield()
        assertEquals("קרית אריה", saved?.name)
        assertEquals("32.0935124", saved?.latitude)
        assertFalse(importer.state.value.busy)
    }
    @Test fun emptyNameFallsBackAndCoordinatesAreAutomatic() = runBlocking {
        val importer = PlaceImport(this, "Place 5", PlaceDraft("", ""), { error("No request expected") }, 0)
        importer.address("https://waze.com/ul?ll=32.08,34.78")
        var saved: PlaceDraft? = null
        importer.save { saved = it }
        yield()
        assertEquals("Place 5", saved?.name)
        assertEquals("32.08", saved?.latitude)
    }
    @Test fun replacingLinkClearsOldCoordinatesAndRejectsLateReply() = runBlocking {
        val old = CompletableDeferred<PlaceResolveResult>()
        val importer = PlaceImport(this, "Place 1", PlaceDraft("Place 1", ""), {
            if (it.endsWith("old")) withContext(NonCancellable) { old.await() } else reply
        }, 0)
        importer.address("https://maps.app.goo.gl/old")
        yield()
        importer.address("https://maps.app.goo.gl/new")
        assertEquals("", importer.state.value.latitude)
        yield()
        old.complete(PlaceResolveResult("Wrong old place", 31.0, 35.0))
        yield()
        assertEquals("קרית אריה", importer.state.value.name)
        assertEquals("32.0935124", importer.state.value.latitude)
    }
    @Test fun failedResolutionCanBeRetriedWithoutLosingInput() = runBlocking {
        var fail = true
        val importer = PlaceImport(this, "Place 1", PlaceDraft("Place 1", ""), {
            if (fail) throw IOException("offline") else reply
        }, 0)
        importer.address(short)
        yield()
        assertNotNull(importer.state.value.error)
        assertEquals(short, importer.state.value.address)
        fail = false
        importer.retry()
        yield()
        assertNull(importer.state.value.error)
        assertEquals("32.0935124", importer.state.value.latitude)
    }
    @Test fun canceledImportCannotChangeClosedEditor() = runBlocking {
        val pending = CompletableDeferred<PlaceResolveResult>()
        val importer = PlaceImport(this, "Place 1", PlaceDraft("Place 1", ""), { withContext(NonCancellable) { pending.await() } }, 0)
        importer.address(short)
        yield()
        importer.cancel()
        pending.complete(reply)
        yield()
        assertEquals("", importer.state.value.latitude)
        assertFalse(importer.state.value.busy)
    }
    @Test fun invalidBackendCoordinatesBlockSaving() = runBlocking {
        val importer = PlaceImport(this, "Place 1", PlaceDraft("", short), { reply.copy(latitude = 100.0) }, 0)
        var saved = false
        importer.save { saved = true }
        yield()
        assertFalse(saved)
        assertNotNull(importer.state.value.error)
    }
}
