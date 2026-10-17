package com.tripplanner

import com.google.gson.JsonParser
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

class RouteTransportTest {
    @Test fun preservesProxyPrefixAndApiContract() = runBlocking {
        val server = MockWebServer()
        server.start()
        try {
            val api = Retrofit.Builder().baseUrl(server.url("/trip-planner/"))
                .addConverterFactory(GsonConverterFactory.create()).build().create(RouteService::class.java)
            val request = RouteRequest(7, RoutePoint("start", 32.0, 34.0), RoutePoint("end", 31.0, 35.0), emptyList())
            for ((manual, path) in listOf(false to "optimize", true to "calculate")) {
                val status = if (manual) "manual" else "optimized"
                server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""{"revision":7,"orderedStopIds":[],"distanceMeters":123,"legDistancesMeters":[123],"status":"$status"}"""))
                val result = if (manual) api.calculate(request) else api.optimize(request)
                validateRoute(result, request, manual)
                val received = requireNotNull(server.takeRequest(5, TimeUnit.SECONDS))
                assertEquals("/trip-planner/v1/routes/$path", received.path)
                assertEquals("POST", received.method)
                val body = JsonParser.parseString(received.body.readUtf8()).asJsonObject
                assertEquals(7, body["revision"].asInt)
                assertEquals("start", body["start"].asJsonObject["id"].asString)
                assertEquals(0, body["stops"].asJsonArray.size())
            }
        } finally { server.shutdown() }
    }
}
