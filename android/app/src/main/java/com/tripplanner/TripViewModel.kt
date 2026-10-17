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

    fun select(id: String?) { saved["tripId"] = id; saved["screen"] = "locations" }
    fun showEndpoints() { saved["screen"] = "endpoints" }
    fun showLocations() { saved["screen"] = "locations" }
    fun acceptShare(text: String) { saved["share"] = text.take(16000) }
    fun clearShare() { saved["share"] = null }

    private fun write(action: suspend () -> Unit) {
        if (saving.value) return
        saving.value = true
        viewModelScope.launch {
            try { action() }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { error.value = "Could not save changes. Please try again." }
            finally { saving.value = false }
        }
    }

    fun createTrip(title: String) {
        if (title.isBlank()) return
        write {
            val id = UUID.randomUUID().toString()
            dao.insertTrip(Trip(id, title.trim()))
            select(id)
        }
    }

    fun saveLocation(existing: TripLocation?, name: String, address: String, lat: Double?, lon: Double?, source: String? = null, shared: Boolean = false) {
        val id = selectedId.value ?: return
        write {
            dao.saveLocation(TripLocation(existing?.id ?: UUID.randomUUID().toString(), id, name.trim(), address.trim(), lat, lon, source ?: existing?.source, existing?.createdAt ?: System.currentTimeMillis()))
            if (shared) clearShare()
        }
    }

    fun remove(location: TripLocation) { write { dao.removeLocation(location) } }
    fun endpoint(location: TripLocation, start: Boolean) {
        val id = selectedId.value ?: return
        write { dao.setEndpoint(id, location.id, start) }
    }
}
