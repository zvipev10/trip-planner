import Foundation

struct PlannerError: LocalizedError {
    let message: String
    init(_ message: String) { self.message = message }
    var errorDescription: String? { message }
}

struct Place: Codable, Identifiable, Equatable {
    var id = UUID()
    var name: String
    var address: String
    var latitude: Double?
    var longitude: Double?
    var resolved: Bool {
        guard let latitude, let longitude else { return false }
        return latitude.isFinite && longitude.isFinite && (-90...90).contains(latitude) && (-180...180).contains(longitude)
    }
}

struct RoutePlan: Codable, Equatable {
    let revision: Int
    let orderedStopIDs: [UUID]
    let distanceMeters: Int
}

struct Trip: Codable, Identifiable {
    var id = UUID()
    var title: String
    var places: [Place] = []
    var startID: UUID?
    var endID: UUID?
    var revision = 0
    var plan: RoutePlan?

    mutating func changed() { revision += 1; plan = nil }
    var start: Place? { places.first { $0.id == startID } }
    var end: Place? { places.first { $0.id == endID } }
}

struct RoutePoint: Codable {
    let id: String
    let latitude: Double
    let longitude: Double
}
struct RoadPolicy: Codable {
    let avoidTolls = false
    let avoidFerries = true
    let avoidUnpaved = true
}
struct RouteRequest: Encodable {
    let revision: Int
    let start: RoutePoint
    let end: RoutePoint
    let stops: [RoutePoint]
    let roadPolicy = RoadPolicy()

    init(trip: Trip) throws {
        guard let first = trip.start, let last = trip.end else { throw PlannerError("Choose both a starting point and an ending point.") }
        guard trip.places.allSatisfy({ $0.resolved }) else { throw PlannerError("Confirm coordinates for every location before optimizing.") }
        guard Set(trip.places.map(\.id)).count == trip.places.count else { throw PlannerError("The trip contains duplicate location IDs.") }
        let middle = trip.places.filter { $0.id != first.id && $0.id != last.id }
        guard middle.count <= 20 else { throw PlannerError("The first version supports up to 20 intermediate stops.") }
        revision = trip.revision
        // Separate request-local endpoint roles also support equal-coordinate round trips.
        start = RoutePoint(id: "start", latitude: first.latitude!, longitude: first.longitude!)
        end = RoutePoint(id: "end", latitude: last.latitude!, longitude: last.longitude!)
        stops = middle.map { RoutePoint(id: $0.id.uuidString, latitude: $0.latitude!, longitude: $0.longitude!) }
    }
}

struct RouteReply: Decodable {
    let revision: Int
    let orderedStopIds: [String]
    let distanceMeters: Int
    let legDistancesMeters: [Int]
    let status: String

    func validated(for request: RouteRequest) throws -> RoutePlan {
        let expected = Set(request.stops.map(\.id))
        guard revision == request.revision, status == "optimized",
              orderedStopIds.count == expected.count, Set(orderedStopIds) == expected,
              legDistancesMeters.count == request.stops.count + 1,
              legDistancesMeters.allSatisfy({ $0 >= 0 && $0 <= 1_000_000_000_000 }),
              distanceMeters >= 0, legDistancesMeters.reduce(0, +) == distanceMeters else {
            throw PlannerError("The server returned an inconsistent route. Please retry.")
        }
        let ids = orderedStopIds.compactMap(UUID.init(uuidString:))
        guard ids.count == orderedStopIds.count else { throw PlannerError("The server returned unknown locations.") }
        return RoutePlan(revision: revision, orderedStopIDs: ids, distanceMeters: distanceMeters)
    }
}

func sharedCoordinates(_ text: String) -> (Double, Double)? {
    func parse(_ value: String) -> (Double, Double)? {
        let cleaned = value.hasPrefix("loc:") ? String(value.dropFirst(4)) : value
        let parts = cleaned.split(separator: ",", omittingEmptySubsequences: false).map { Double($0.trimmingCharacters(in: .whitespacesAndNewlines)) }
        guard parts.count == 2, let lat = parts[0], let lon = parts[1], lat.isFinite, lon.isFinite,
              (-90...90).contains(lat), (-180...180).contains(lon) else { return nil }
        return (lat, lon)
    }
    if let pair = parse(text.trimmingCharacters(in: .whitespacesAndNewlines)) { return pair }
    guard let expression = try? NSRegularExpression(pattern: "https?://[^\\s]+"),
          let match = expression.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
          let range = Range(match.range, in: text), let url = URLComponents(string: String(text[range])) else { return nil }
    for key in ["ll", "q", "query"] {
        if let value = url.queryItems?.first(where: { $0.name == key })?.value, let pair = parse(value) { return pair }
    }
    return nil
}
