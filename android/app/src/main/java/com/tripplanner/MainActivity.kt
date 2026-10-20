package com.tripplanner

import android.content.Intent
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
import androidx.compose.runtime.saveable.listSaver
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

class MainActivity : ComponentActivity() {
    private val model: TripViewModel by viewModels()
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (savedInstanceState == null) receiveShare(intent)
        setContent {
            TripTheme {
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
    val routing by model.routing.collectAsStateWithLifecycle()
    val routePlan by model.plan.collectAsStateWithLifecycle()
    val failedLocations by model.failedLocations.collectAsStateWithLifecycle()
    val trip = activeTrip?.takeIf { it.id == selectedId }
    val locations = allLocations.filter { it.tripId == selectedId }
    var creating by rememberSaveable { mutableStateOf(false) }
    var editingId by rememberSaveable(selectedId) { mutableStateOf<String?>(null) }
    var adding by rememberSaveable(selectedId) { mutableStateOf(false) }
    var importing by rememberSaveable(selectedId) { mutableStateOf(false) }
    var arrivalId by rememberSaveable(selectedId) { mutableStateOf<String?>(null) }
    var editEndpoints by rememberSaveable(selectedId) { mutableStateOf(false) }
    var endpointPicker by rememberSaveable(selectedId) { mutableStateOf<String?>(null) }

    BackHandler(enabled = selectedId != null && !adding && editingId == null && !importing && endpointPicker == null) {
        if (screen == "endpoints") model.showLocations() else model.select(null)
    }
    Scaffold(topBar = {
        TopAppBar(
            title = {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    BrandMark()
                    Column {
                        Text("Trip Planner", style = MaterialTheme.typography.titleMedium)
                        Text("LESS DISTANCE. MORE DISCOVERY.", style = MaterialTheme.typography.labelSmall, fontSize = 8.sp)
                    }
                }
            },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = WebPaper),
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
                Card(colors = CardDefaults.cardColors(containerColor = WebInk), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("MAKE ROOM FOR THE JOURNEY", color = WebLime, style = MaterialTheme.typography.labelSmall)
                        Text("A better order\nto your day.", color = Color.White, style = MaterialTheme.typography.headlineLarge)
                        Text("Gather your places. Find a shorter drive.", color = WebLime)
                        Button(onClick = { creating = true }, enabled = !saving,
                            colors = ButtonDefaults.buttonColors(containerColor = WebLime, contentColor = WebInk)) { Text("Create a trip ↗") }
                    }
                }
                Text("Your trips", style = MaterialTheme.typography.titleLarge)
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
                Text(trip.title, style = MaterialTheme.typography.headlineLarge, maxLines = 2)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = screen != "endpoints", onClick = model::showLocations, label = { Text("1 · Collect places") })
                    FilterChip(selected = screen == "endpoints", onClick = model::showEndpoints, label = { Text("2 · Plan route") })
                }
                if (screen == "endpoints") {
                    Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("2 · Start and end", style = MaterialTheme.typography.headlineSmall)
                        Text("Endpoints are saved. Use the same place for a round trip.")
                        if (trip.startId == null || trip.endId == null || editEndpoints) {
                        EndpointCard("Starting point", locations.find { it.id == trip.startId }) { endpointPicker = "start" }
                        EndpointCard("Ending point", locations.find { it.id == trip.endId }) { endpointPicker = "end" }
                        } else {
                            Text("Start: ${locations.find { it.id == trip.startId }?.name.orEmpty()}")
                            Text("End: ${locations.find { it.id == trip.endId }?.name.orEmpty()}")
                        }
                        TextButton(onClick = { editEndpoints = !editEndpoints }) { Text(if (editEndpoints) "Done editing endpoints" else "Edit start & end") }
                        locations.filter { it.id in failedLocations }.forEach { place ->
                            OutlinedCard(Modifier.fillMaxWidth()) {
                                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                    Text("Location needs attention", fontWeight = FontWeight.Bold)
                                    Text(place.name, style = MaterialTheme.typography.titleMedium)
                                    Text("No nearby driving road. Choose an arrival point; original destination stays saved. Access unverified.")
                                    Button(onClick = { arrivalId = place.id }, enabled = !saving && !routing) { Text("Choose arrival point") }
                                    OutlinedButton(onClick = { editingId = place.id }) { Text("Edit location") }
                                    if (place.arrivalLatitude != null) TextButton(onClick = { model.arrival(place, null, null) }) { Text("Reset to original location") }
                                }
                            }
                        }
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
                                Button(onClick = { model.calculateRoute() }, enabled = selectedEndpoints && unresolved == 0 && !saving && !routing) { Text("Optimize shortest route") }
                                if (routing) {
                                    LinearProgressIndicator(Modifier.fillMaxWidth())
                                    TextButton(onClick = model::cancelRoute) { Text("Cancel") }
                                }
                                val current = routePlan?.takeIf { it.tripId == trip.id && it.revision == trip.revision }
                                if (current != null) {
                                    Card(colors = CardDefaults.cardColors(containerColor = WebInk), modifier = Modifier.fillMaxWidth()) {
                                        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                            Text(if (current.distance == null) "ORDER CHANGED" else if (current.manual) "YOUR CHOSEN ORDER" else "OPTIMIZED ROUTE", color = WebLime, style = MaterialTheme.typography.labelSmall)
                                            Text(current.distance?.let { String.format(java.util.Locale.getDefault(), "%.2f km", it / 1000.0) } ?: "Recalculate distance", color = Color.White, style = MaterialTheme.typography.headlineLarge)
                                            Text(if (current.distance == null) "The previous distance no longer applies." else "Approximate road distance.", color = WebLime)
                                        }
                                    }
                                    Text(if (current.manual) "Manual order" else "Optimized order", fontWeight = FontWeight.Bold)
                                    RouteStop("START", locations.find { it.id == trip.startId }?.name.orEmpty(), "S")
                                    current.order.forEachIndexed { index, id ->
                                        RouteStop("STOP ${index + 1}", locations.find { it.id == id }?.name ?: id, "${index + 1}")
                                        Row {
                                            TextButton(onClick = { model.moveStop(index, -1) }, enabled = index > 0 && !routing && !saving) { Text("Move up") }
                                            TextButton(onClick = { model.moveStop(index, 1) }, enabled = index < current.order.lastIndex && !routing && !saving) { Text("Move down") }
                                        }
                                    }
                                    RouteStop("END", locations.find { it.id == trip.endId }?.name.orEmpty(), "E")
                                    OutlinedButton(onClick = { model.calculateRoute(true) }, enabled = !routing && !saving) { Text("Calculate this order") }
                                    if (current.distance != null) RouteMap(trip, locations, current)
                                    Text("Last calculated route and endpoints are saved on this device. Editing locations requires recalculation.", style = MaterialTheme.typography.bodySmall)
                                }
                            }
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
            TextButton(enabled = title.isNotBlank() && !saving, onClick = { model.createTrip(title) { creating = false } }) { Text("Create") }
        }, dismissButton = { TextButton(onClick = { creating = false }) { Text("Cancel") } })
    }
    val arrivalPlace = locations.find { it.id == arrivalId }
    if (arrivalPlace != null) {
        var lat by rememberSaveable(arrivalPlace.id) { mutableStateOf((arrivalPlace.arrivalLatitude ?: arrivalPlace.latitude)?.toString().orEmpty()) }
        var lon by rememberSaveable(arrivalPlace.id) { mutableStateOf((arrivalPlace.arrivalLongitude ?: arrivalPlace.longitude)?.toString().orEmpty()) }
        val latitude = lat.toDoubleOrNull(); val longitude = lon.toDoubleOrNull()
        val valid = latitude != null && longitude != null && latitude.isFinite() && longitude.isFinite() && latitude in -90.0..90.0 && longitude in -180.0..180.0
        AlertDialog(onDismissRequest = { arrivalId = null }, title = { Text("Choose arrival point") }, text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(arrivalPlace.name)
                Text("Original destination stays saved. Tap the map or enter coordinates. Access unverified.")
                if (arrivalPlace.latitude != null && arrivalPlace.longitude != null) ArrivalMap(arrivalPlace) { a, b -> lat = a.toString(); lon = b.toString() }
                OutlinedTextField(value = lat, onValueChange = {lat = it}, label = {Text("Arrival latitude")})
                OutlinedTextField(value = lon, onValueChange = {lon = it}, label = {Text("Arrival longitude")})
                if (valid && arrivalPlace.latitude != null && arrivalPlace.longitude != null) {
                    val meters = FloatArray(1)
                    android.location.Location.distanceBetween(arrivalPlace.latitude, arrivalPlace.longitude, latitude!!, longitude!!, meters)
                    Text("${meters[0].toInt()} m from original destination")
                }
            }
        }, confirmButton = { TextButton(enabled = valid && !saving, onClick = {model.arrival(arrivalPlace, latitude, longitude); arrivalId = null}) {Text("Use this arrival point")} }, dismissButton = {TextButton(onClick = {arrivalId = null}) {Text("Cancel")}})
    }
    val editing = locations.find { it.id == editingId }
    if (trip != null && (adding || editing != null || importing)) {
        LocationEditor(
            existing = editing,
            fallbackNumber = locations.size + 1,
            shared = if (importing) shared else null,
            saving = saving,
            saveError = error,
            close = { adding = false; editingId = null; importing = false },
            save = { name, address, lat, lon ->
                model.saveLocation(editing, name, address, lat, lon, if (importing) shared else null, importing) {
                    adding = false; editingId = null; importing = false
                }
            },
            remove = editing?.let { { model.remove(it) { editingId = null } } },
        )
    }
    if (endpointPicker != null) {
        AlertDialog(onDismissRequest = { endpointPicker = null }, title = { Text(if (endpointPicker == "start") "Starting point" else "Ending point") }, text = {
            LazyColumn {
                items(locations, key = { it.id }) { place ->
                    TextButton(onClick = { model.endpoint(place, endpointPicker == "start") { endpointPicker = null } }, enabled = !saving, modifier = Modifier.fillMaxWidth()) { Text(place.name) }
                }
            }
        }, confirmButton = {}, dismissButton = { TextButton(onClick = { endpointPicker = null }) { Text("Cancel") } })
    }
}

@Composable
private fun RouteStop(label: String, name: String, marker: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.small) {
            Box(Modifier.size(36.dp), contentAlignment = Alignment.Center) { Text(marker, fontWeight = FontWeight.Bold) }
        }
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(name, style = MaterialTheme.typography.titleMedium)
        }
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

private val draftSaver = listSaver<PlaceDraft, Any>(
    save = { listOf(it.name, it.address, it.latitude, it.longitude, it.autoName) },
    restore = { PlaceDraft(it[0] as String, it[1] as String, it[2] as String, it[3] as String, it[4] as Boolean) },
)

@Composable
private fun LocationEditor(existing: TripLocation?, fallbackNumber: Int, shared: String?, saving: Boolean, saveError: String?, close: () -> Unit, save: (String, String, Double?, Double?) -> Unit, remove: (() -> Unit)?) {
    val scope = rememberCoroutineScope()
    val fallback = "Place $fallbackNumber"
    val initialCoordinates = sharedCoordinates(shared)
    var savedDraft by rememberSaveable(existing?.id, shared, stateSaver = draftSaver) {
        mutableStateOf(PlaceDraft(
            existing?.name ?: sharedPlaceName(shared.orEmpty()) ?: fallback,
            existing?.address ?: shared.orEmpty(),
            (existing?.latitude ?: initialCoordinates?.first)?.toString().orEmpty(),
            (existing?.longitude ?: initialCoordinates?.second)?.toString().orEmpty(),
            autoName = existing?.name.isNullOrBlank(),
        ))
    }
    val importer = remember(existing?.id, shared) {
        PlaceImport(scope, fallback, savedDraft, { text -> routeService().resolvePlace(PlaceResolveRequest(text)) })
    }
    val draft by importer.state.collectAsStateWithLifecycle()
    SideEffect { savedDraft = draft.copy(busy = false, saving = false, error = null) }
    LaunchedEffect(importer) {
        if (draft.latitude.isBlank() && draft.longitude.isBlank() && draft.address.isNotBlank()) importer.retry()
    }
    DisposableEffect(importer) { onDispose { importer.cancel() } }
    val working = saving || draft.saving
    val dismiss = { importer.cancel(); close() }
    AlertDialog(onDismissRequest = dismiss, title = { Text(if (existing == null) "Add location" else "Edit location") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedTextField(draft.name, importer::name, enabled = !working, label = { Text("Place name (optional)") }, singleLine = true)
            OutlinedTextField(draft.address, importer::address, enabled = !working, label = { Text("Address or shared link") }, minLines = 2, maxLines = 4)
            Text("Paste a Google Maps or Waze destination link. Its name and coordinates fill automatically when available.", style = MaterialTheme.typography.bodySmall)
            if (draft.busy) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text("Reading map link…")
            }
            OutlinedTextField(draft.latitude, importer::latitude, enabled = !working, label = { Text("Latitude") }, singleLine = true)
            OutlinedTextField(draft.longitude, importer::longitude, enabled = !working, label = { Text("Longitude") }, singleLine = true)
            TextButton(onClick = importer::retry, enabled = !working && draft.address.isNotBlank()) { Text("Retry link extraction") }
            if (draft.error != null) Text(draft.error!!, color = MaterialTheme.colorScheme.error)
            if (saveError != null) Text(saveError, color = MaterialTheme.colorScheme.error)
            if (remove != null) TextButton(onClick = remove, enabled = !working) { Text("Remove from trip") }
        }
    }, confirmButton = {
        TextButton(enabled = !working, onClick = {
            importer.save { value -> save(value.name, value.address, value.latitude.toDoubleOrNull(), value.longitude.toDoubleOrNull()) }
        }) { Text(if (draft.saving) "Reading link…" else "Save") }
    }, dismissButton = { TextButton(onClick = dismiss, enabled = !saving) { Text("Cancel") } })
}
