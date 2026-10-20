# Route diagnostic logging

Scope: diagnose the reported round-trip HTTP 422 without logging coordinates, names, links, request bodies, or point IDs. Existing route behavior and API responses remain unchanged.

Plan: add sanitized validation summaries and routing error codes; test diagnostic usefulness and privacy; deploy the reviewed branch and verify public health.

Review: unknown validation fields must be replaced with a fixed placeholder; never serialize Pydantic input or context. No new dependencies.

Checkpoint: implementation and regression test ready. Local Python lacks pytest; run tests using the existing VM environment before activating the change.

Publishing: dedicated fix/route-diagnostic-logging branch; no direct main push.

Operator command: sudo journalctl -u trip-planner --since '10 minutes ago' --no-pager

Next: verify tests, deploy, reproduce the failing trip, inspect request_validation_failed or routing_failure records. No architecture or product-context update needed.
