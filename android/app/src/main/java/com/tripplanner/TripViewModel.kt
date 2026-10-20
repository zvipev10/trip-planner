package com.tripplanner

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalCoroutinesApi::class)
class TripViewModel(application: Application, private val saved: SavedStateHandle) : AndroidViewModel(application) {
    private val dao = TripDatabase.get(application).trips()
    val trips = dao.summaries().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val selectedId = saved.getStateFlow<String?>("tripId", null)
    val screen = saved.getStateFlow("screen", "locations")
    val pendingShare = saved.getStateFlow<String?>("share", null)
    val error = MutableStateFlow<String?>(null)
    val saving = MutableStateFlow(false)
    val trip = selectedId.flatMapLatest { id -> if (id == null) flowOf(null) else dao.trip(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
    val locations = selectedId.flatMapLatest { id -> if (id == null) flowOf(emptyList()) else dao.locations(id) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val plan = MutableStateFlow<RoutePlan?>(null)
    val routing = MutableStateFlow(false)
    val failedLocations = MutableStateFlow<List<String>>(emptyList())
    private var routeGeneration = 0L
    private var routeJob: kotlinx.coroutines.Job? = null

    fun cancelRoute() { routeGeneration++; routeJob?.cancel(); routeJob = null; routing.value = false }

    fun moveStop(index: Int, delta: Int) {
        if (routing.value || saving.value) return
        val current = plan.value ?: return
        val target = index + delta
        if (index !in current.order.indices || target !in current.order.indices) return
        val order = current.order.toMutableList()
        java.util.Collections.swap(order, index, target)
        plan.value = current.copy(order = order, distance = null, manual = true, geometry = null)
    }

    fun calculateRoute(manual: Boolean = false) {
        val id = selectedId.value ?: return
        if (routing.value || saving.value) return
        val generation = ++routeGeneration
        routing.value = true
        error.value = null
        failedLocations.value = emptyList()
        routeJob = viewModelScope.launch {
            try {
                val snapshot = requireNotNull(dao.snapshot(id)) { "Trip no longer exists." }
                val previous = plan.value?.takeIf { it.tripId == id && it.revision == snapshot.trip.revision }
                val request = routeRequest(snapshot, if (manual) requireNotNull(previous) { "Optimize the route first." }.order else null)
                val service = routeService()
                val result = validateRoute(if (manual) service.calculate(request) else service.optimize(request), request, manual)
                if (generation == routeGeneration && selectedId.value == id && dao.findTrip(id)?.revision == request.revision) {
                    val resultPlan = RoutePlan(id, request.revision, requireNotNull(result.orderedStopIds), result.distanceMeters, manual, validatedGeometry(result.geometry))
                    dao.saveRoute(id, request.revision, com.google.gson.Gson().toJson(resultPlan))
                    plan.value = resultPlan
                }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: retrofit2.HttpException) {
                val detail = runCatching { com.google.gson.JsonParser.parseString(failure.response()?.errorBody()?.string()).asJsonObject.getAsJsonObject("error") }.getOrNull()
                if (detail?.get("code")?.asString == "location_not_routable") {
                    val currentTrip = dao.findTrip(id)
                    failedLocations.value = detail.getAsJsonArray("locationIds")?.mapNotNull {
                        when (val key = it.asString) { "endpoint:start" -> currentTrip?.startId; "endpoint:end" -> currentTrip?.endId; else -> key }
                    }?.distinct() ?: emptyList()
                }
                error.value = when (failure.code()) {
                    422 -> "Server rejected these locations. Check endpoints and coordinates."
                    503 -> "Routing is unavailable. Please try again later."
                    else -> "Routing failed (HTTP ${failure.code()}). Please try again."
                }
            } catch (_: java.io.IOException) { error.value = "Could not reach the routing server. Check your connection and retry." }
            catch (failure: IllegalArgumentException) { error.value = failure.message ?: "Invalid route. Check your locations." }
            catch (_: Exception) { error.value = "Could not calculate the route. Please try again." }
            finally { if (generation == routeGeneration) routing.value = false }
        }
    }

    init {
        viewModelScope.launch {
            trip.collect { item ->
                if (item != null && item.id == selectedId.value && plan.value?.revision != item.revision) {
                    dao.snapshot(item.id)?.let { plan.value = restoredPlan(item.routeJson, it) }
                }
            }
        }
    }

    fun select(id: String?) {
        cancelRoute(); plan.value = null; failedLocations.value = emptyList(); error.value = null
        saved["tripId"] = id; saved["screen"] = "locations"
        if (id != null) viewModelScope.launch {
            val snapshot = dao.snapshot(id) ?: return@launch
            if (selectedId.value == id) {
                plan.value = restoredPlan(snapshot.trip.routeJson, snapshot)
                if (snapshot.trip.startId != null && snapshot.trip.endId != null) saved["screen"] = "endpoints"
            }
        }
    }

    fun arrival(place: TripLocation, lat: Double?, lon: Double?) {
        require((lat == null && lon == null) || (lat != null && lon != null && lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0))
        write(onSuccess = { saving.value = false; calculateRoute() }) { dao.saveLocation(place.copy(arrivalLatitude = lat, arrivalLongitude = lon)) }
    }
    fun showEndpoints() { saved["screen"] = "endpoints" }
    fun showLocations() { saved["screen"] = "locations" }
    fun acceptShare(text: String) { saved["share"] = text.take(16000) }
    fun clearShare() { saved["share"] = null }

    private fun write(onSuccess: () -> Unit = {}, action: suspend () -> Unit) {
        if (saving.value) return
        cancelRoute()
        plan.value = null
        failedLocations.value = emptyList()
        saving.value = true
        error.value = null
        viewModelScope.launch {
            try { action(); onSuccess() }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { error.value = "Could not save changes. Please try again." }
            finally { saving.value = false }
        }
    }

    fun createTrip(title: String, onSaved: () -> Unit = {}) {
        if (title.isBlank()) return
        write(onSuccess = onSaved) {
            val id = UUID.randomUUID().toString()
            dao.insertTrip(Trip(id, title.trim()))
            select(id)
        }
    }

    fun saveLocation(existing: TripLocation?, name: String, address: String, lat: Double?, lon: Double?, source: String? = null, shared: Boolean = false, onSaved: () -> Unit = {}) {
        val id = selectedId.value ?: return
        write(onSuccess = onSaved) {
            dao.saveLocation(TripLocation(existing?.id ?: UUID.randomUUID().toString(), id, name.trim().ifBlank { sharedPlaceName(address) ?: "Place ${(dao.snapshot(id)?.locations?.size ?: 0) + 1}" }, address.trim(), lat, lon, source ?: existing?.source, existing?.createdAt ?: System.currentTimeMillis(), existing?.arrivalLatitude?.takeIf { existing.latitude == lat && existing.longitude == lon }, existing?.arrivalLongitude?.takeIf { existing.latitude == lat && existing.longitude == lon }))
            if (shared && pendingShare.value == source) clearShare()
        }
    }

    fun remove(location: TripLocation, onSaved: () -> Unit = {}) { write(onSuccess = onSaved) { dao.removeLocation(location) } }
    fun endpoint(location: TripLocation, start: Boolean, onSaved: () -> Unit = {}) {
        val id = selectedId.value ?: return
        write(onSuccess = onSaved) { dao.setEndpoint(id, location.id, start) }
    }
}
