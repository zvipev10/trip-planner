import Foundation

struct RouteClient {
    let baseURL: URL
    let session: URLSession
    init(baseURL: URL = URL(string: "http://151.145.93.180/trip-planner/")!, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }
    func optimize(_ payload: RouteRequest) async throws -> RoutePlan {
        #if !DEBUG
        guard baseURL.scheme == "https" else { throw PlannerError("A secure HTTPS backend must be configured for release builds.") }
        #endif
        var request = URLRequest(url: baseURL.appendingPathComponent("v1/routes/optimize"))
        request.httpMethod = "POST"
        request.timeoutInterval = 90
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(payload)
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw PlannerError("The server returned an invalid response.") }
        guard (200..<300).contains(response.statusCode) else {
            switch response.statusCode {
            case 422: throw PlannerError("The route could not be calculated. Confirm the locations and try again.")
            case 429, 503: throw PlannerError("The routing service is busy or unavailable. Please retry shortly.")
            case 504: throw PlannerError("The route calculation timed out. Try fewer stops.")
            default: throw PlannerError("The server could not calculate this route (HTTP \(response.statusCode)).")
            }
        }
        return try JSONDecoder().decode(RouteReply.self, from: data).validated(for: payload)
    }
}
