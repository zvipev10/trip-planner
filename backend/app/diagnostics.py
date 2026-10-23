"""Bounded routing diagnostics without user location data."""
from contextvars import ContextVar
import json
import logging

request_id = ContextVar("routing_request_id", default="unassigned")


def event(name: str, **fields):
    logging.getLogger("uvicorn.error").info("planning_diagnostic %s", json.dumps({"requestId": request_id.get(), "event": name, **fields}, separators=(",", ":")))
