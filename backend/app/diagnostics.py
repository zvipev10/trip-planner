"""Routing diagnostics including user-authorized replay payloads and coordinates."""
from contextvars import ContextVar
import json
import logging

request_id = ContextVar("routing_request_id", default="unassigned")


def event(name: str, **fields):
    logging.getLogger("uvicorn.error").info("planning_diagnostic %s", json.dumps({"requestId": request_id.get(), "event": name, **fields}, separators=(",", ":")))
