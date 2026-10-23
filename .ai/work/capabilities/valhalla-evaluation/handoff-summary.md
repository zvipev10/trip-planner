# Evaluation results

Tested the actual logged five-point request with Valhalla's public demo using five HTTP calls total: strict single leg, default single leg, locate, full shortest trip permitting unpaved, and full trip with default costing excluding unpaved. No original trip modifications and no production engine switch.

- Routino current policy: third intermediate stop disconnected.
- Valhalla shortest + hierarchy pruning disabled + exclude_unpaved + exclude_ferries: no path to affected stop (442).
- Valhalla default car: affected leg succeeds, 46.316 km.
- Locate: dirt-track candidate roughly 504 m from pin; paved service-road candidate roughly 673 m away. Therefore success does not imply arrival at original pin or a paved entrance.
- Full five-point route in submitted order, shortest + hierarchy pruning disabled + ferries excluded + unpaved permitted: succeeds, four legs, 97.625 km. This is a comparison of fixed submitted order, not optimized visiting order. Some legs have very long estimated times; route suitability needs inspection.
- Full five-point route, default car + unpaved excluded: no path (442).

Conclusion: another engine can produce a route if unpaved roads are permitted, but engine replacement alone does not resolve the user's current policy. Earlier Routino tests permitting tracks/unpaved still failed, so engine/data/snapping differences also contribute. Do not silently relax policy or move destination. Recommend an explicit unpaved option and arrival confirmation, then revalidate shortest matrix/route consistency before a production Valhalla trial.

Sources: https://valhalla.github.io/valhalla/api/route/api-reference/ and https://valhalla.github.io/valhalla/start/introduction/. Demo is not configured for app traffic. No private coordinates, point IDs or raw payloads in this artifact. Replay inputs remain in server journal. No new runtime dependencies.

QA complete: 74 backend tests passed, 1 optional skipped, existing Starlette deprecation warning. Dedicated comparison test verifies round-trip endpoints/stop order, shortest options, original road policy and explicit unpaved override without mutation. Production integration deliberately remains inactive because strict policy also fails and endpoint snapping is substantial. All existing app capabilities retained. No APK or app deployment needed; comparison tool can run independently. Next product decision: explicitly allow unpaved trials and confirm actual arrival points before adding a selectable provider. PR #12 contains tool and results.
