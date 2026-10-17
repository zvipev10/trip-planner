package com.tripplanner

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

class MainActivity : ComponentActivity() {
    private val model: TripViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (savedInstanceState == null) receiveShare(intent)
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(primary = Color(0xFF146B58), secondary = Color(0xFF42675D))) {
                TripApp(model)
            }
        }
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        receiveShare(intent)
    }
    private fun receiveShare(intent: Intent) {
        if (intent.action == Intent.ACTION_SEND && intent.type == "text/plain") {
            intent.getStringExtra(Intent.EXTRA_TEXT)?.takeIf { it.isNotBlank() }?.let(model::acceptShare)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TripApp(model: TripViewModel) {
    val trips by model.trips.collectAsStateWithLifecycle()
    val selectedId by model.selectedId.collectAsStateWithLifecycle()
    val activeTrip by model.trip.collectAsStateWithLifecycle()
    val allLocations by model.locations.collectAsStateWithLifecycle()
    val screen by model.screen.collectAsStateWithLifecycle()
    val shared by model.pendingShare.collectAsStateWithLifecycle()
    val error by model.error.collectAsStateWithLifecycle()
    val saving by model.saving.collectAsStateWithLifecycle()
    val trip = activeTrip?.takeIf { it.id == selectedId }
    val locations = allLocations.filter { it.tripId == selectedId }
    var creating by rememberSaveable { mutableStateOf(false) }
    var editingId by rememberSaveable(selectedId) { mutableStateOf<String?>(null) }
    var adding by rememberSaveable(selectedId) { mutableStateOf(false) }
    var importing by rememberSaveable(selectedId) { mutableStateOf(false) }
    var endpointPicker by rememberSaveable(selectedId) { mutableStateOf<String?>(null) }

    BackHandler(enabled = selectedId != null && !adding && editingId == null && !importing && endpointPicker == null) {
        if (screen == "endpoints") model.showLocations() else model.select(null)
    }
    Scaffold(topBar = {
        TopAppBar(
            title = { Text(if (selectedId == null) "Your trips" else trip?.title ?: "Loading trip…") },
            navigationIcon = {
                if (selectedId != null) TextButton(onClick = { if (screen == "endpoints") model.showLocations() else model.select(null) }) { Text("Back") }
            },
        )
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (error != null) {
                Text(error!!, color = MaterialTheme.colorScheme.error)
                TextButton(onClick = { model.error.value = null }) { Text("Dismiss") }
            }
            if (shared != null) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Shared place", fontWeight = FontWeight.Bold)
                        Text(if (selectedId == null) "Choose a trip below, or create a new trip." else "Add this place to ${trip?.title ?: "this trip"}.")
                        Row {
                            if (trip != null) TextButton(onClick = { importing = true }, enabled = !saving) { Text("Review place") }
                            TextButton(onClick = model::clearShare) { Text("Dismiss share") }
                        }
                    }
                }
            }
            if (selectedId == null) {
                Text("Collect places, then plan the shortest driving route.", style = MaterialTheme.typography.bodyLarge)
                Button(onClick = { creating = true }, enabled = !saving) { Text("Create trip") }
                if (trips.isEmpty()) Text("Your saved trips will appear here.")
                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(trips, key = { it.trip.id }) { item ->
                        OutlinedCard(Modifier.fillMaxWidth().clickable { model.select(item.trip.id) }) {
                            Column(Modifier.padding(18.dp)) {
                                Text(item.trip.title, style = MaterialTheme.typography.titleMedium)
                                Text("${item.locationCount} locations")
                            }
                        }
                    }
                }
            } else if (trip != null) {
                if (screen == "endpoints") {
                    Text("2 · Start and end", style = MaterialTheme.typography.headlineSmall)
                    Text("Choose both endpoints. Use the same place for a round trip, or choose different places.")
                    EndpointCard("Starting point", locations.find { it.id == trip.startId }) { endpointPicker = "start" }
                    EndpointCard("Ending point", locations.find { it.id == trip.endId }) { endpointPicker = "end" }
                    OutlinedButton(onClick = { adding = true }, enabled = !saving) { Text("Add another place") }
                    val selectedEndpoints = trip.startId != null && trip.endId != null
                    val unresolved = locations.count { !it.resolved }
                    Card {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("Planning status", fontWeight = FontWeight.Bold)
                            Text(when {
                                !selectedEndpoints -> "Select a starting point and an ending point."
                                unresolved > 0 -> "$unresolved locations still need a confirmed map position."
                                else -> "Your locations and endpoints are saved."
                            })
                            Text("Route optimization will be available after the routing service is connected.")
                        }
                    }
                } else {
                    Text("1 · Collect locations", style = MaterialTheme.typography.headlineSmall)
                    Text("Add places now and come back to plan later. Changes save on this device.")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { adding = true }, enabled = !saving) { Text("Add location") }
                        OutlinedButton(onClick = model::showEndpoints, enabled = locations.isNotEmpty()) { Text("Start and end") }
                    }
                    if (locations.isEmpty()) Text("No locations yet. Add an address, coordinates, or a shared link.")
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        items(locations, key = { it.id }) { place ->
                            OutlinedCard(Modifier.fillMaxWidth().clickable { editingId = place.id }) {
                                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(place.name, style = MaterialTheme.typography.titleMedium)
                                    if (place.address.isNotBlank()) Text(place.address, maxLines = 3)
                                    Text(if (place.resolved) "${place.latitude}, ${place.longitude}" else "Needs confirmed coordinates", style = MaterialTheme.typography.labelMedium)
                                    val roles = listOfNotNull("Start".takeIf { place.id == trip.startId }, "End".takeIf { place.id == trip.endId })
                                    if (roles.isNotEmpty()) Text(roles.joinToString(" · "), color = MaterialTheme.colorScheme.primary)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    if (creating) {
        var title by rememberSaveable { mutableStateOf("") }
        AlertDialog(onDismissRequest = { creating = false }, title = { Text("Create trip") }, text = {
            OutlinedTextField(value = title, onValueChange = { title = it.take(120) }, label = { Text("Trip title") }, singleLine = true)
        }, confirmButton = {
            TextButton(enabled = title.isNotBlank() && !saving, onClick = { model.createTrip(title); creating = false }) { Text("Create") }
        }, dismissButton = { TextButton(onClick = { creating = false }) { Text("Cancel") } })
    }
    val editing = locations.find { it.id == editingId }
    if (trip != null && (adding || editing != null || importing)) {
        LocationEditor(
            existing = editing,
            shared = if (importing) shared else null,
            saving = saving,
            close = { adding = false; editingId = null; importing = false },
            save = { name, address, lat, lon ->
                model.saveLocation(editing, name, address, lat, lon, if (importing) shared else null, importing)
                adding = false; editingId = null; importing = false
            },
            remove = editing?.let { { model.remove(it); editingId = null } },
        )
    }
    if (endpointPicker != null) {
        AlertDialog(onDismissRequest = { endpointPicker = null }, title = { Text(if (endpointPicker == "start") "Starting point" else "Ending point") }, text = {
            LazyColumn {
                items(locations, key = { it.id }) { place ->
                    TextButton(onClick = { model.endpoint(place, endpointPicker == "start"); endpointPicker = null }, enabled = !saving, modifier = Modifier.fillMaxWidth()) { Text(place.name) }
                }
            }
        }, confirmButton = {}, dismissButton = { TextButton(onClick = { endpointPicker = null }) { Text("Cancel") } })
    }
}

@Composable
private fun EndpointCard(label: String, place: TripLocation?, choose: () -> Unit) {
    OutlinedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(label, style = MaterialTheme.typography.labelLarge)
            Text(place?.name ?: "Not selected", style = MaterialTheme.typography.titleMedium)
            TextButton(onClick = choose) { Text(if (place == null) "Choose place" else "Change") }
        }
    }
}

private fun sharedCoordinates(text: String?): Pair<Double, Double>? {
    if (text == null) return null
    val candidate = runCatching {
        val uri = Uri.parse(text.trim())
        uri.getQueryParameter("ll") ?: uri.getQueryParameter("q") ?: uri.getQueryParameter("query") ?: text.trim()
    }.getOrDefault(text.trim())
    val parts = candidate.split(",").map { it.trim().toDoubleOrNull() }
    return if (parts.size == 2 && parts[0] != null && parts[1] != null && parts[0]!!.isFinite() && parts[1]!!.isFinite() && parts[0]!! in -90.0..90.0 && parts[1]!! in -180.0..180.0) parts[0]!! to parts[1]!! else null
}

@Composable
private fun LocationEditor(existing: TripLocation?, shared: String?, saving: Boolean, close: () -> Unit, save: (String, String, Double?, Double?) -> Unit, remove: (() -> Unit)?) {
    val initial = remember(shared) { sharedCoordinates(shared) }
    var name by rememberSaveable(existing?.id, shared) { mutableStateOf(existing?.name ?: "") }
    var address by rememberSaveable(existing?.id, shared) { mutableStateOf(existing?.address ?: shared ?: "") }
    var latitude by rememberSaveable(existing?.id, shared) { mutableStateOf((existing?.latitude ?: initial?.first)?.toString() ?: "") }
    var longitude by rememberSaveable(existing?.id, shared) { mutableStateOf((existing?.longitude ?: initial?.second)?.toString() ?: "") }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(onDismissRequest = close, title = { Text(if (existing == null) "Add location" else "Edit location") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedTextField(name, { name = it.take(200) }, label = { Text("Place name") }, singleLine = true)
            OutlinedTextField(address, { address = it.take(16000) }, label = { Text("Address or shared link") }, minLines = 2, maxLines = 4)
            Text("Coordinates are optional while collecting places. Addresses and short links will need resolution before routing.", style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(latitude, { latitude = it }, label = { Text("Latitude") }, singleLine = true)
            OutlinedTextField(longitude, { longitude = it }, label = { Text("Longitude") }, singleLine = true)
            if (initial != null) Text("Coordinates extracted from shared text. Please confirm the destination.")
            if (error != null) Text(error!!, color = MaterialTheme.colorScheme.error)
            if (remove != null) TextButton(onClick = remove, enabled = !saving) { Text("Remove from trip") }
        }
    }, confirmButton = {
        TextButton(enabled = !saving, onClick = {
            val lat = latitude.toDoubleOrNull()
            val lon = longitude.toDoubleOrNull()
            val coordinatesEntered = latitude.isNotBlank() || longitude.isNotBlank()
            error = when {
                name.isBlank() -> "Enter a place name."
                coordinatesEntered && (lat == null || lon == null || !lat.isFinite() || !lon.isFinite() || lat !in -90.0..90.0 || lon !in -180.0..180.0) -> "Enter valid latitude and longitude."
                !coordinatesEntered && address.isBlank() -> "Enter an address, link, or coordinates."
                else -> null
            }
            if (error == null) save(name, address, lat, lon)
        }) { Text("Save") }
    }, dismissButton = { TextButton(onClick = close) { Text("Cancel") } })
}
