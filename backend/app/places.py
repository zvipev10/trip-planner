"""Resolve only known map hosts; never follow redirects to arbitrary servers."""
import asyncio
import html
import json
import math
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit

import httpx
from pydantic import Field

from .models import Model
from .provider import PlanningError


class DestinationMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = None
        self.title = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href")
        if tag == "meta" and values.get("property") == "og:url" and not self.canonical:
            self.canonical = values.get("content")
        if tag == "meta" and values.get("property") == "og:title":
            self.title = values.get("content")


class PlaceLinkRequest(Model):
    text: str = Field(min_length=1, max_length=16000)


HOSTS = {"maps.app.goo.gl", "goo.gl", "google.com", "www.google.com", "maps.google.com", "google.co.il", "www.google.co.il", "maps.google.co.il", "waze.com", "www.waze.com", "ul.waze.com"}


def allowed(url):
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.hostname in HOSTS and port in (None, 443) and not parsed.username and not parsed.password


def parse_place(text):
    link = re.search(r"https?://[^\s<>]+", text)
    raw = link.group().rstrip('.,;)\"') if link else text.strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return {"name": None}
    query = parse_qs(parsed.query)
    name = None
    match = re.search(r"/maps/place/([^/]+)", parsed.path)
    if match:
        candidate = unquote(match[1]).replace("+", " ")
        if not re.fullmatch(r"[-\d., +]+", candidate):
            name = candidate[:200]
    for key in ("q", "query"):
        value = query.get(key, [""])[0]
        if value and not re.fullmatch(r"(?:loc:)?[-\d., +]+", value) and not value.startswith("place_id:"):
            name = name or value[:200]
    for key in ("name", "venue_name"):
        name = name or query.get(key, [None])[0]
    coordinate = None
    geohash = re.search(r"/ul/h([0-9bcdefghjkmnpqrstuvwxyz]{6,12})(?:$|/)", parsed.path)
    if parsed.hostname in {"waze.com", "www.waze.com", "ul.waze.com"} and geohash:
        bounds, axis = [[-180.0, 180.0], [-90.0, 90.0]], 0
        for char in geohash[1]:
            value = "0123456789bcdefghjkmnpqrstuvwxyz".index(char)
            for bit in range(4, -1, -1):
                bound = bounds[axis]
                middle = sum(bound) / 2
                bound[0 if (value >> bit) & 1 else 1] = middle
                axis = 1 - axis
        coordinate = {"latitude": sum(bounds[1]) / 2, "longitude": sum(bounds[0]) / 2}
    candidates = [raw] if not link else [query.get(k, [""])[0] for k in ("destination", "ll", "q", "query")]
    # Google place coordinates, unlike @lat,lon camera positions, identify a destination.
    data = re.search(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)", unquote(raw))
    if data:
        candidates.insert(0, f"{data[1]},{data[2]}")
    for candidate in candidates:
        match = re.fullmatch(r"(?:loc:)?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*(?:\([^)]*\))?", candidate)
        if match:
            lat, lon = map(float, match.groups())
            if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                coordinate = {"latitude": lat, "longitude": lon}
                break
    return {"name": name[:200] if name else None, **(coordinate or {})}


def google_embed_url(url):
    """Keep the exact Google feature ID, dropping tracking and camera parameters."""
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    ftid = query.get("ftid", [""])[0]
    if parsed.hostname not in {"google.com", "www.google.com", "maps.google.com", "google.co.il", "www.google.co.il", "maps.google.co.il"} or not re.fullmatch(r"0x[0-9a-fA-F]+:0x[0-9a-fA-F]+", ftid):
        return url, None
    return "https://www.google.com/maps?" + urlencode({"q": query.get("q", [ftid])[0], "ftid": ftid, "output": "embed", "hl": "en"}), ftid


def embedded_google_place(page, expected_ftid):
    if not expected_ftid:
        return None
    start = re.search(r"\binitEmbed\s*\(\s*", page)
    if not start:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(page[start.end():])
    except (ValueError, RecursionError):
        return None

    def find(node, label=None):
        if not isinstance(node, list):
            return None
        if len(node) >= 3 and node[0] == expected_ftid and isinstance(node[1], str) and isinstance(node[2], list) and len(node[2]) == 2:
            lat, lon = node[2]
            if type(lat) in (int, float) and type(lon) in (int, float):
                point = parse_place(f"{lat},{lon}")
                if "latitude" in point:
                    return {**point, "name": (label or node[1])[:200]}
        for child in node:
            child_label = node[1] if isinstance(node[0], list) and len(node) > 1 and isinstance(node[1], str) else None
            result = find(child, child_label)
            if result:
                return result
        return None

    try:
        return find(payload)
    except (RecursionError, IndexError):
        return None


async def resolve_place(text, client=None):
    result = parse_place(text)
    if "latitude" in result:
        return result
    link = re.search(r"https?://[^\s<>]+", text)
    if not link:
        raise PlanningError("unresolved_place", "Paste a Google Maps or Waze destination link containing a map position.")
    url = link.group().rstrip('.,;)\"')
    # Normalize original HTTP map links to HTTPS before making an external request.
    if url.startswith("http://"):
        url = "https://" + url[7:]
    if not allowed(url):
        raise PlanningError("unsupported_link", "Use a Google Maps or Waze link.")
    if client is None:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=True) as session:
            try:
                async with asyncio.timeout(20):
                    return await resolve_place(text, session)
            except TimeoutError as exc:
                raise PlanningError("link_resolution_failed", "Reading this map link timed out. Please retry.", 504) from exc
    try:
        expected_ftid = None
        for _ in range(6):
            url, feature_id = google_embed_url(url)
            expected_ftid = feature_id or expected_ftid
            if not allowed(url):
                raise PlanningError("unsupported_redirect", "This map link redirects to an unsupported website.")
            async with client.stream("GET", url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"}) as response:
                if response.is_redirect and response.headers.get("location"):
                    url = urljoin(url, response.headers["location"])
                    parsed = parse_place(url)
                    if not allowed(url):
                        raise PlanningError("unsupported_redirect", "This map link redirects to an unsupported website.")
                    result = {**result, **{k: v for k, v in parsed.items() if v is not None}}
                    if "latitude" in result:
                        return result
                    continue
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 1_000_000:
                        break
                page = html.unescape(body[:1_000_000].decode("utf-8", errors="replace"))
                embedded = embedded_google_place(page, expected_ftid)
                if embedded:
                    return embedded
                # Resolve canonical destination metadata, not unrelated map markers in page scripts.
                metadata = DestinationMetadata()
                metadata.feed(page)
                if metadata.canonical:
                    detail = parse_place(metadata.canonical)
                    result.update({k: v for k, v in detail.items() if v is not None})
                if metadata.title:
                    result["name"] = re.sub(r"\s*[-–]\s*(Google Maps|Waze).*$", "", metadata.title)[:200]
                if "latitude" in result:
                    return result
                break
    except (httpx.HTTPError, ValueError) as exc:
        raise PlanningError("link_resolution_failed", "Could not open this map link. Please retry or paste the full destination link.", 502) from exc
    raise PlanningError("unresolved_place", "This link did not expose a destination position. Open the place in Maps or Waze and copy its destination link again.")
