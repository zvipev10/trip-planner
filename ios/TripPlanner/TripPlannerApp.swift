import SwiftUI

@main
@MainActor
struct TripPlannerApp: App {
    @StateObject private var store = TripStore()
    var body: some Scene {
        WindowGroup {
            TripsView().environmentObject(store).tint(Color(red: 0.08, green: 0.42, blue: 0.34))
        }
    }
}

struct TripsView: View {
    @EnvironmentObject private var store: TripStore
    @State private var creating = false
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Collect places, then plan the shortest driving route.")
                        .foregroundStyle(.secondary)
                    Button("Create trip", systemImage: "plus") { creating = true }
                }
                Section("Saved trips") {
                    if store.trips.isEmpty { Text("Your trips will appear here.").foregroundStyle(.secondary) }
                    ForEach(store.trips) { trip in
                        NavigationLink(destination: TripDetail(id: trip.id)) {
                            VStack(alignment: .leading) {
                                Text(trip.title).font(.headline)
                                Text("\(trip.places.count) locations").font(.subheadline).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Your trips")
            .sheet(isPresented: $creating) { CreateTripView() }
            .alert("Trip Planner", isPresented: Binding(get: { store.error != nil }, set: { if !$0 { store.error = nil } })) {
                Button("OK") { store.error = nil }
            } message: { Text(store.error ?? "") }
        }
    }
}

struct CreateTripView: View {
    @EnvironmentObject private var store: TripStore
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    var body: some View {
        NavigationStack {
            Form { TextField("Trip title", text: $title) }
                .navigationTitle("Create trip")
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Create") { if store.create(title) != nil { dismiss() } }
                            .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
        }
    }
}

struct TripDetail: View {
    let id: UUID
    @EnvironmentObject private var store: TripStore
    @State private var adding = false
    @State private var editing: Place?
    var body: some View {
        Group {
            if let trip = store.trip(id) {
                List {
                    Section {
                        Text("1 · Collect locations").font(.headline)
                        Text("Paste an address or shared Google Maps/Waze link. Confirm coordinates before routing.")
                            .font(.subheadline).foregroundStyle(.secondary)
                        Button("Add location", systemImage: "plus") { adding = true }
                        NavigationLink("2 · Choose start and end") { EndpointsView(id: id) }
                            .disabled(trip.places.isEmpty)
                    }
                    Section("Locations") {
                        if trip.places.isEmpty { Text("No locations yet.").foregroundStyle(.secondary) }
                        ForEach(trip.places) { place in
                            Button { editing = place } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(place.name).font(.headline).foregroundStyle(.primary)
                                    if !place.address.isEmpty { Text(place.address).font(.subheadline).lineLimit(2).foregroundStyle(.secondary) }
                                    Text(place.resolved ? "Coordinates confirmed" : "Needs coordinates").font(.caption).foregroundStyle(.secondary)
                                    if place.id == trip.startID || place.id == trip.endID {
                                        Text([place.id == trip.startID ? "Start" : nil, place.id == trip.endID ? "End" : nil].compactMap { $0 }.joined(separator: " · ")).font(.caption)
                                    }
                                }
                            }
                        }
                        .onDelete { indices in
                            let removed = indices.map { trip.places[$0] }
                            for place in removed { store.remove(place, in: id) }
                        }
                    }
                }
                .navigationTitle(trip.title)
                .sheet(isPresented: $adding) { PlaceEditor(tripID: id, place: nil) }
                .sheet(item: $editing) { place in PlaceEditor(tripID: id, place: place) }
            } else { Text("Trip not found.") }
        }
    }
}

struct EndpointsView: View {
    let id: UUID
    @EnvironmentObject private var store: TripStore
    var body: some View {
        Group {
            if let trip = store.trip(id) {
                List {
                    Section("Start and end") {
                        Text("Use the same place for a round trip, or select different endpoints.")
                        Picker("Starting point", selection: Binding<UUID?>(get: { store.trip(id)?.startID }, set: { value in store.change(id) { $0.startID = value } })) {
                            Text("Choose a place").tag(nil as UUID?)
                            ForEach(trip.places) { Text($0.name).tag($0.id as UUID?) }
                        }
                        Picker("Ending point", selection: Binding<UUID?>(get: { store.trip(id)?.endID }, set: { value in store.change(id) { $0.endID = value } })) {
                            Text("Choose a place").tag(nil as UUID?)
                            ForEach(trip.places) { Text($0.name).tag($0.id as UUID?) }
                        }
                    }
                    Section {
                        if store.busy.contains(id) {
                            HStack { ProgressView(); Text("Optimizing route…") }
                        } else {
                            Button(trip.plan == nil ? "Optimize route" : "Optimize again") { Task { await store.optimize(id) } }
                                .disabled(trip.startID == nil || trip.endID == nil || trip.places.contains { !$0.resolved })
                        }
                        let unresolved = trip.places.filter { !$0.resolved }.count
                        if unresolved > 0 { Text("\(unresolved) locations need coordinates. Edit them in the location list.").foregroundStyle(.secondary) }
                    }
                    if let plan = trip.plan, plan.revision == trip.revision {
                        Section("Optimized route") {
                            Text(Measurement(value: Double(plan.distanceMeters) / 1000, unit: UnitLength.kilometers), format: .measurement(width: .abbreviated, usage: .asProvided))
                                .font(.title2.bold())
                            Text("Approximate driving distance").font(.caption).foregroundStyle(.secondary)
                            if let start = trip.start { Text("Start · \(start.name)") }
                            ForEach(Array(plan.orderedStopIDs.enumerated()), id: \.element) { index, placeID in
                                if let place = trip.places.first(where: { $0.id == placeID }) { Text("\(index + 1). \(place.name)") }
                            }
                            if let end = trip.end { Text("End · \(end.name)") }
                        }
                    }
                    Section {
                        Text("Road data © OpenStreetMap contributors. Routing: Routino. Routes reflect imported road data; current closures may differ.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                .navigationTitle("Plan route")
            } else { Text("Trip not found.") }
        }
    }
}

struct PlaceEditor: View {
    let tripID: UUID
    let place: Place?
    @EnvironmentObject private var store: TripStore
    @Environment(\.dismiss) private var dismiss
    @State private var name: String
    @State private var address: String
    @State private var latitude: String
    @State private var longitude: String
    @State private var message: String?

    init(tripID: UUID, place: Place?) {
        self.tripID = tripID; self.place = place
        _name = State(initialValue: place?.name ?? "")
        _address = State(initialValue: place?.address ?? "")
        _latitude = State(initialValue: place?.latitude.map { String($0) } ?? "")
        _longitude = State(initialValue: place?.longitude.map { String($0) } ?? "")
    }
    var body: some View {
        NavigationStack {
            Form {
                Section("Location") {
                    TextField("Place name", text: $name)
                    TextField("Address or shared link", text: $address, axis: .vertical).lineLimit(2...4)
                    Button("Extract coordinates from pasted text") {
                        guard let pair = sharedCoordinates(address) else {
                            message = "This text does not contain explicit coordinates. Short links and addresses need manual coordinates for now."; return
                        }
                        latitude = String(pair.0); longitude = String(pair.1)
                        message = "Coordinates extracted. Please confirm the destination."
                    }
                }
                Section("Coordinates") {
                    TextField("Latitude", text: $latitude).keyboardType(.numbersAndPunctuation)
                    TextField("Longitude", text: $longitude).keyboardType(.numbersAndPunctuation)
                    Text("Optional while collecting places; required before optimization.").font(.caption)
                }
                if let message { Section { Text(message) } }
                if let error = store.error { Section { Text(error).foregroundStyle(.red) } }
            }
            .navigationTitle(place == nil ? "Add location" : "Edit location")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save", action: save) }
            }
        }
    }
    private func save() {
        let latText = latitude.trimmingCharacters(in: .whitespacesAndNewlines)
        let lonText = longitude.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanName.isEmpty else { message = "Enter a place name."; return }
        let hasCoordinates = !latText.isEmpty || !lonText.isEmpty
        let updated = Place(id: place?.id ?? UUID(), name: String(cleanName.prefix(200)), address: String(address.prefix(16000)), latitude: Double(latText), longitude: Double(lonText))
        if hasCoordinates && !updated.resolved { message = "Enter valid latitude and longitude."; return }
        if !hasCoordinates && address.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { message = "Enter an address, link, or coordinates."; return }
        if store.save(updated, in: tripID) { dismiss() }
    }
}
