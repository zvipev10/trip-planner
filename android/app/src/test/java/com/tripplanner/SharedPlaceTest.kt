package com.tripplanner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SharedPlaceTest {
    @Test fun wazeEncodedDestinationPreservesLatitudeOrder() {
        assertEquals(32.08 to 34.78, sharedCoordinates("https://waze.com/ul?ll=32.08%2C34.78&navigate=yes"))
    }
    @Test fun googleMapsExplicitCoordinateQuery() {
        assertEquals(31.78 to 35.22, sharedCoordinates("https://www.google.com/maps/search/?api=1&query=31.78%2C35.22"))
    }
    @Test fun sharedTitleDoesNotHideLink() {
        assertEquals(32.08 to 34.78, sharedCoordinates("Meet here\nhttps://waze.com/ul?ll=32.08,34.78"))
    }
    @Test fun acceptsPastedCoordinatePair() {
        assertEquals(32.08 to 34.78, sharedCoordinates(" 32.08, 34.78 "))
    }
    @Test fun cameraPositionIsNotADestination() {
        assertNull(sharedCoordinates("https://www.google.com/maps/@32.08,34.78,15z"))
    }
    @Test fun unresolvedAddressesAndShortLinksStayUnresolved() {
        assertNull(sharedCoordinates("https://maps.app.goo.gl/example"))
        assertNull(sharedCoordinates("https://maps.google.com/?q=Tel+Aviv"))
        assertNull(sharedCoordinates("Tel Aviv 12"))
    }
    @Test fun malformedAndOutOfRangeCoordinatesAreRejected() {
        for (text in listOf("91,34", "32,181", "NaN,34", "32,Infinity", "32,34,35", "https://waze.com/ul?ll=%ZZ")) {
            assertNull(text, sharedCoordinates(text))
        }
    }
    @Test fun hebrewSharedLabelIsPreservedOutsideParser() {
        assertEquals(32.08 to 34.78, sharedCoordinates("תל אביב\nhttps://waze.com/ul?ll=32.08,34.78"))
    }
}
