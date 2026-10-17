import XCTest
@testable import TripPlanner

final class PlannerTests: XCTestCase {
    private func place(_ name: String) -> Place { Place(name: name, address: "", latitude: 32.08, longitude: 34.78) }
    func testDifferentEndpointsAreNotIntermediateStops() throws {
        let a = place("A"), b = place("B"), c = place("C")
        let request = try RouteRequest(trip: Trip(title: "Test", places: [a,b,c], startID: a.id, endID: c.id))
        XCTAssertEqual(request.stops.map(\.id), [b.id.uuidString])
        XCTAssertNotEqual(request.start.id, request.end.id)
    }
    func testRoundTripHasSeparateEndpointRoles() throws {
        let a = place("A"), b = place("B")
        let request = try RouteRequest(trip: Trip(title: "Loop", places: [a,b], startID: a.id, endID: a.id))
        XCTAssertEqual(request.start.latitude, request.end.latitude)
        XCTAssertNotEqual(request.start.id, request.end.id)
        XCTAssertEqual(request.stops.count, 1)
    }
    func testUnresolvedLocationBlocksOptimization() {
        let a = place("A"), b = Place(name: "B", address: "Jerusalem")
        XCTAssertThrowsError(try RouteRequest(trip: Trip(title: "Test", places: [a,b], startID: a.id, endID: b.id)))
    }
    func testIntermediateLimit() {
        let places = (0..<23).map { place("\($0)") }
        XCTAssertThrowsError(try RouteRequest(trip: Trip(title: "Large", places: places, startID: places.first!.id, endID: places.last!.id)))
    }
    func testReplyCannotLoseStopsOrUseOldRevision() throws {
        let a = place("A"), b = place("B")
        let request = try RouteRequest(trip: Trip(title: "Loop", places: [a,b], startID: a.id, endID: a.id))
        let missing = RouteReply(revision: 0, orderedStopIds: [], distanceMeters: 100, legDistancesMeters: [100], status: "optimized")
        XCTAssertThrowsError(try missing.validated(for: request))
        let stale = RouteReply(revision: 1, orderedStopIds: [b.id.uuidString], distanceMeters: 100, legDistancesMeters: [40,60], status: "optimized")
        XCTAssertThrowsError(try stale.validated(for: request))
    }
    func testValidReplyAndJSONContract() throws {
        let a = place("A"), b = place("B")
        let request = try RouteRequest(trip: Trip(title: "Loop", places: [a,b], startID: a.id, endID: a.id))
        let reply = RouteReply(revision: 0, orderedStopIds: [b.id.uuidString], distanceMeters: 100, legDistancesMeters: [40,60], status: "optimized")
        XCTAssertEqual(try reply.validated(for: request).orderedStopIDs, [b.id])
        let json = try JSONSerialization.jsonObject(with: JSONEncoder().encode(request)) as! [String: Any]
        XCTAssertNotNil(json["roadPolicy"])
        XCTAssertEqual((json["start"] as? [String:Any])?["id"] as? String, "start")
    }
    func testSharedLinksAndCameraPositions() {
        XCTAssertEqual(sharedCoordinates("https://waze.com/ul?ll=32.08%2C34.78")?.0, 32.08)
        XCTAssertEqual(sharedCoordinates("תל אביב\nhttps://maps.google.com/?q=32.08,34.78")?.1, 34.78)
        XCTAssertNil(sharedCoordinates("https://maps.google.com/maps/@32.08,34.78,15z"))
        XCTAssertNil(sharedCoordinates("https://maps.app.goo.gl/example"))
        XCTAssertNil(sharedCoordinates("91,34"))
    }
    @MainActor func testPersistenceAndEndpointRemoval() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appendingPathComponent("trips.json")
        let store = TripStore(file: file)
        let id = try XCTUnwrap(store.create("Weekend"))
        let a = place("A")
        XCTAssertTrue(store.save(a, in: id))
        store.change(id) { $0.startID = a.id; $0.endID = a.id }
        let reopened = TripStore(file: file)
        XCTAssertEqual(reopened.trip(id)?.startID, a.id)
        reopened.remove(a, in: id)
        XCTAssertNil(reopened.trip(id)?.startID)
        XCTAssertNil(reopened.trip(id)?.endID)
    }
    @MainActor func testUnreadableStorageIsNotOverwritten() async throws {
        let file = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: file) }
        let original = Data("invalid-json".utf8)
        try original.write(to: file)
        let store = TripStore(file: file)
        XCTAssertNil(store.create("Must not overwrite"))
        XCTAssertEqual(try Data(contentsOf: file), original)
    }
}
