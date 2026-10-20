package com.tripplanner

import com.google.gson.Gson
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

internal suspend fun importPlace(text: String, remote: suspend (String) -> PlaceResolveResult): PlaceResolveResult? {
    val name = sharedPlaceName(text)
    sharedCoordinates(text)?.let { return PlaceResolveResult(name, it.first, it.second) }
    if (!Regex("https?://").containsMatchIn(text)) return null
    val reply = remote(text)
    require(reply.latitude != null && reply.longitude != null && reply.latitude.isFinite() && reply.longitude.isFinite() && reply.latitude in -90.0..90.0 && reply.longitude in -180.0..180.0) { "The link did not provide valid destination coordinates." }
    return reply.copy(name = reply.name?.trim()?.takeIf { it.isNotEmpty() }?.take(200) ?: name)
}

internal data class PlaceDraft(
    val name: String, val address: String, val latitude: String = "", val longitude: String = "",
    val autoName: Boolean = true, val busy: Boolean = false, val saving: Boolean = false, val error: String? = null,
)

internal class PlaceImport(
    private val scope: CoroutineScope,
    private val fallback: String,
    initial: PlaceDraft,
    private val remote: suspend (String) -> PlaceResolveResult,
    private val debounceMillis: Long = 300,
) {
    private val mutable = MutableStateFlow(initial)
    val state = mutable.asStateFlow()
    private var job: Job? = null
    private var generation = 0L

    fun name(value: String) { mutable.value = mutable.value.copy(name = value.take(200), autoName = value.isBlank()) }
    fun latitude(value: String) { cancel(); mutable.value = mutable.value.copy(latitude = value, busy = false) }
    fun longitude(value: String) { cancel(); mutable.value = mutable.value.copy(longitude = value, busy = false) }
    fun address(value: String) {
        cancel()
        val text = value.take(16000)
        val old = mutable.value
        mutable.value = old.copy(address = text, latitude = "", longitude = "", error = null,
            name = if (old.autoName) sharedPlaceName(text) ?: fallback else old.name)
        schedule(debounceMillis)
    }
    fun retry() { cancel(); schedule(0) }
    fun cancel() { generation++; job?.cancel(); job = null; mutable.value = mutable.value.copy(busy = false, saving = false) }

    private fun schedule(wait: Long) {
        val token = generation
        job = scope.launch {
            delay(wait)
            resolve(token)
        }
    }
    private suspend fun resolve(token: Long): Boolean {
        val source = mutable.value.address.trim()
        mutable.value = mutable.value.copy(busy = true, error = null)
        try {
            val details = importPlace(source, remote)
            if (token != generation) return false
            val current = mutable.value
            mutable.value = current.copy(
                name = if (current.autoName) details?.name ?: sharedPlaceName(source) ?: fallback else current.name,
                latitude = details?.latitude?.toString() ?: current.latitude,
                longitude = details?.longitude?.toString() ?: current.longitude,
            )
            return true
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (failure: Exception) {
            if (token == generation) mutable.value = mutable.value.copy(error = message(failure))
            return false
        } finally {
            if (token == generation) mutable.value = mutable.value.copy(busy = false)
        }
    }
    fun save(onSave: (PlaceDraft) -> Unit) {
        if (mutable.value.saving) return
        cancel()
        val token = generation
        mutable.value = mutable.value.copy(saving = true, error = null)
        job = scope.launch {
            try {
                if (mutable.value.latitude.isBlank() && mutable.value.longitude.isBlank() && !resolve(token)) return@launch
                if (token != generation) return@launch
                val draft = mutable.value
                val lat = draft.latitude.toDoubleOrNull()
                val lon = draft.longitude.toDoubleOrNull()
                val hasCoordinates = draft.latitude.isNotBlank() || draft.longitude.isNotBlank()
                require(!hasCoordinates || (lat != null && lon != null && lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0)) { "Enter valid latitude and longitude." }
                require(hasCoordinates || draft.address.isNotBlank()) { "Enter an address, link, or coordinates." }
                onSave(draft.copy(name = draft.name.trim().ifBlank { fallback }))
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: Exception) { if (token == generation) mutable.value = mutable.value.copy(error = message(failure)) }
            finally { if (token == generation) mutable.value = mutable.value.copy(saving = false) }
        }
    }
}

private data class ImportErrorBody(val error: ImportError?)
private data class ImportError(val message: String?)
private fun message(failure: Exception): String = when (failure) {
    is retrofit2.HttpException -> if (failure.code() == 404) "Update the backend to enable map-link resolution." else
        runCatching { Gson().fromJson(failure.response()?.errorBody()?.string(), ImportErrorBody::class.java)?.error?.message?.take(400) }.getOrNull()
            ?: "Could not read this map link. Retry extraction."
    is java.io.IOException -> "Could not reach the server. Check your connection and retry extraction."
    is IllegalArgumentException -> failure.message ?: "Check this place's coordinates."
    else -> "Could not read this map link. Retry extraction."
}
