import Foundation
import SwiftUI

@MainActor
final class TripStore: ObservableObject {
    @Published private(set) var trips: [Trip] = []
    @Published private(set) var busy: Set<UUID> = []
    @Published var error: String?
    private let file: URL
    private var readable = true
    private let client: RouteClient

    init(file: URL? = nil, client: RouteClient = RouteClient()) {
        self.file = file ?? URL.applicationSupportDirectory.appendingPathComponent("TripPlanner/trips.json")
        self.client = client
        if FileManager.default.fileExists(atPath: self.file.path) {
            do { trips = try JSONDecoder().decode([Trip].self, from: Data(contentsOf: self.file)) }
            catch { readable = false; self.error = "Saved trips could not be loaded. Your data has been kept unchanged." }
        }
    }
    func trip(_ id: UUID) -> Trip? { trips.first { $0.id == id } }
    @discardableResult
    private func commit(_ updated: [Trip]) -> Bool {
        guard readable else { error = "Saved data needs recovery before changes can be saved."; return false }
        do {
            try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
            try JSONEncoder().encode(updated).write(to: file, options: .atomic)
            trips = updated
            return true
        } catch { self.error = "Could not save changes. Please retry."; return false }
    }
    @discardableResult
    func create(_ title: String) -> UUID? {
        guard !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }
        let trip = Trip(title: String(title.trimmingCharacters(in: .whitespacesAndNewlines).prefix(120)))
        return commit([trip] + trips) ? trip.id : nil
    }
    @discardableResult
    func change(_ id: UUID, _ edit: (inout Trip) -> Void) -> Bool {
        guard let index = trips.firstIndex(where: { $0.id == id }) else { return false }
        var copy = trips
        edit(&copy[index]); copy[index].changed()
        return commit(copy)
    }
    @discardableResult
    func save(_ place: Place, in id: UUID) -> Bool {
        change(id) { trip in
            if let index = trip.places.firstIndex(where: { $0.id == place.id }) { trip.places[index] = place }
            else { trip.places.append(place) }
        }
    }
    func remove(_ place: Place, in id: UUID) {
        change(id) { trip in
            trip.places.removeAll { $0.id == place.id }
            if trip.startID == place.id { trip.startID = nil }
            if trip.endID == place.id { trip.endID = nil }
        }
    }
    func optimize(_ id: UUID) async {
        guard !busy.contains(id), let snapshot = trip(id) else { return }
        error = nil
        do {
            let request = try RouteRequest(trip: snapshot)
            busy.insert(id)
            defer { busy.remove(id) }
            let plan = try await client.optimize(request)
            guard let index = trips.firstIndex(where: { $0.id == id }), trips[index].revision == snapshot.revision else { return }
            var copy = trips; copy[index].plan = plan
            commit(copy)
        } catch is CancellationError { }
        catch let failure as PlannerError { error = failure.message }
        catch let failure as URLError {
            error = failure.code == .timedOut ? "The request timed out. Please retry." : "Could not reach the routing service. Check your connection and retry."
        } catch { self.error = "The route response could not be read. Please retry." }
    }
}
