package com.tripplanner

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.view.MotionEvent
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.gson.Gson
import java.io.ByteArrayInputStream

internal data class MapPlace(val id: String, val name: String, val latitude: Double?, val longitude: Double?)
internal data class MapPlan(val order: List<String>, val geometry: List<List<Double>>?, val stale: Boolean = false)
internal data class MapTrip(val places: List<MapPlace>, val startId: String?, val endId: String?, val plan: MapPlan)

internal fun mapPayload(trip: Trip, locations: List<TripLocation>, plan: RoutePlan): MapTrip {
    require(plan.tripId == trip.id && plan.revision == trip.revision && plan.distance != null)
    return MapTrip(locations.filter { it.tripId == trip.id }.map { MapPlace(it.id, it.name, it.latitude, it.longitude) },
        trip.startId, trip.endId, MapPlan(plan.order, plan.geometry))
}

@Composable
fun RouteMap(trip: Trip, locations: List<TripLocation>, plan: RoutePlan) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val view = remember(context) { RouteMapView(context) }
    val json = remember(trip, locations, plan) { Gson().toJson(mapPayload(trip, locations, plan)) }
    DisposableEffect(lifecycle, view) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> view.onResume()
                Lifecycle.Event.ON_PAUSE -> view.onPause()
                else -> Unit
            }
        }
        lifecycle.addObserver(observer)
        if (lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) view.onResume()
        onDispose { lifecycle.removeObserver(observer) }
    }
    AndroidView(factory = { view }, modifier = Modifier.fillMaxWidth().height(440.dp),
        onReset = null, onRelease = { it.onPause(); it.destroy() }, update = { it.setRoute(json) })
}

@SuppressLint("SetJavaScriptEnabled") // Bundled map renderer only; no JavaScript/native bridge.
private class RouteMapView(context: Context) : WebView(context) {
    private var latest: String? = null
    private var ready = false
    private val origin = "appassets.androidplatform.net"
    private val files = mapOf("index.html" to "text/html", "map.css" to "text/css", "leaflet.css" to "text/css",
        "leaflet.js" to "text/javascript", "route-map.mjs" to "text/javascript", "leaflet-LICENSE.txt" to "text/plain")

    init {
        settings.javaScriptEnabled = true
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        settings.userAgentString += " TripPlanner/0.3.0"
        setBackgroundColor(Color.WHITE)
        webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                val url = request.url
                if (url.scheme == "https" && url.host == origin && url.path?.startsWith("/assets/map/") == true) {
                    val filename = url.path!!.removePrefix("/assets/map/")
                    val mime = files[filename]
                    if (mime != null) return WebResourceResponse(mime, "UTF-8", context.assets.open("map/$filename"))
                }
                if (url.scheme == "https" && url.host == "tile.openstreetmap.org") return null
                return WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", emptyMap(), ByteArrayInputStream(ByteArray(0)))
            }
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (request.url.host == origin && request.url.scheme == "https") return false
                if (request.isForMainFrame && request.url.scheme == "https" && request.url.host in setOf("www.openstreetmap.org", "leafletjs.com")) {
                    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, request.url).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
                }
                return true
            }
            override fun onPageFinished(view: WebView, url: String) {
                if (url == "https://$origin/assets/map/index.html") { ready = true; renderRoute() }
            }
        }
        loadUrl("https://$origin/assets/map/index.html")
    }

    fun setRoute(json: String) {
        if (latest == json) return
        latest = json
        if (ready) renderRoute()
    }

    private fun renderRoute() {
        latest?.let { evaluateJavascript("window.showRoute($it);", null) }
    }

    @SuppressLint("ClickableViewAccessibility") // WebView exposes the map's DOM controls to accessibility services.
    override fun onTouchEvent(event: MotionEvent): Boolean {
        parent?.requestDisallowInterceptTouchEvent(event.actionMasked != MotionEvent.ACTION_UP && event.actionMasked != MotionEvent.ACTION_CANCEL)
        return super.onTouchEvent(event)
    }
}
