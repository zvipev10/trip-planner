# Route diagnostic logging

Scope: diagnose the reported round-trip HTTP 422 without logging coordinates, names, links, request bodies, or point IDs. Existing route behavior and API responses remain unchanged.

Plan: add sanitized validation summaries and routing error codes; test diagnostic usefulness and privacy; deploy the reviewed branch and verify public health.

Review: unknown validation fields must be replaced with a fixed placeholder; never serialize Pydantic input or context. No new dependencies.

Checkpoint: implementation and regression test ready. Local Python lacks pytest; run tests using the existing VM environment before activating the change.

Publishing: dedicated fix/route-diagnostic-logging branch; no direct main push.

Operator command: sudo journalctl -u trip-planner --since '10 minutes ago' --no-pager

Next: verify tests, deploy, reproduce the failing trip, inspect request_validation_failed or routing_failure records. No architecture or product-context update needed.

## Validation and deployment
65 backend tests passed; one optional routing fixture skipped. Public health passed after deployment. An empty optimize request returned the unchanged HTTP 422 response. Deployed commit b6b41a4 on fix/route-diagnostic-logging; PR #1 is draft and unmerged. VM tracks the logging branch until review/merge; return to main after merge. No product behavior or interface change. Follow-up: reproduce the user's actual trip failure and inspect sanitized validation logs.

## Latest production diagnosis — 2026-10-20
The two latest optimize attempts at 20:21:38 and 20:22:06 Asia/Jerusalem failed with HTTP 422 and routing_failure code=location_not_routable. This is a Routino road-snapping failure, not endpoint-ID validation. The sanitized logs do not identify the affected place. Next step: use the client error's locationIds or a user-exported trip to identify the point and validate its map position and road coverage. No coordinates or user place IDs are included in this handoff.
