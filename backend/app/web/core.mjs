export function uid() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) crypto.getRandomValues(bytes);
  else
    for (let i = 0; i < bytes.length; i++)
      bytes[i] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const s = [...bytes].map((n) => n.toString(16).padStart(2, "0")).join("");
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20)}`;
}
export function newTrip(title) {
  if (!title.trim()) throw Error("Enter a trip title.");
  return {
    id: uid(),
    title: title.trim().slice(0, 120),
    places: [],
    startId: "",
    endId: "",
    revision: 0,
    plan: null,
  };
}
export function resolved(p) {
  return (
    typeof p.latitude === "number" &&
    Number.isFinite(p.latitude) &&
    Math.abs(p.latitude) <= 90 &&
    typeof p.longitude === "number" &&
    Number.isFinite(p.longitude) &&
    Math.abs(p.longitude) <= 180
  );
}
export function coordinates(text) {
  const pair = (s) => {
    const v = s
      .replace(/^loc:/, "")
      .split(",")
      .map((x) => x.trim());
    if (v.length !== 2 || v.some((x) => !x)) return null;
    const p = { latitude: Number(v[0]), longitude: Number(v[1]) };
    return resolved(p) ? p : null;
  };
  if (pair(text.trim())) return pair(text.trim());
  const link = text.match(/https?:\/\/[^\s]+/);
  if (!link) return null;
  try {
    const url = new URL(link[0]);
    const destination = decodeURIComponent(url.href).match(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/);
    if (destination && pair(`${destination[1]},${destination[2]}`)) return pair(`${destination[1]},${destination[2]}`);
    const hash = /(?:^|\.)waze\.com$/.test(url.hostname) && url.pathname.match(/\/ul\/h([0-9bcdefghjkmnpqrstuvwxyz]{6,12})(?:$|\/)/);
    if (hash) {
      const bounds = [[-180, 180], [-90, 90]];
      let axis = 0;
      for (const char of hash[1]) {
        const value = "0123456789bcdefghjkmnpqrstuvwxyz".indexOf(char);
        for (let bit = 4; bit >= 0; bit--) {
          const b = bounds[axis], mid = (b[0] + b[1]) / 2;
          b[(value >> bit) & 1 ? 0 : 1] = mid;
          axis = 1 - axis;
        }
      }
      return { latitude: (bounds[1][0] + bounds[1][1]) / 2, longitude: (bounds[0][0] + bounds[0][1]) / 2 };
    }
    for (const k of ["destination", "ll", "q", "query"]) {
      const v = url.searchParams.get(k);
      if (v && pair(v)) return pair(v);
    }
  } catch {}
  return null;
}
export function placeName(text, number = 1) {
  const link = text.match(/https?:\/\/[^\s<>]+/);
  if (link) {
    try {
      const url = new URL(link[0]);
      const segment = url.pathname.match(/\/maps\/place\/([^/]+)/);
      if (segment) {
        const name = decodeURIComponent(segment[1]).replace(/\+/g, " ");
        if (!/^[\d.,+ -]+$/.test(name)) return name.slice(0, 200);
      }
      for (const key of ["name", "venue_name", "q", "query"]) {
        const value = url.searchParams.get(key);
        if (value && !/^(?:loc:)?[\d.,+ -]+$/.test(value) && !value.startsWith("place_id:")) return value.slice(0, 200);
      }
      const label = text.slice(0, link.index).trim().replace(/[\s:–-]+$/, "");
      if (label) return label.slice(0, 200);
    } catch {}
  }
  return `Place ${number}`;
}

export function requestFor(trip, manualOrder = null) {
  const first = trip.places.find((p) => p.id === trip.startId),
    last = trip.places.find((p) => p.id === trip.endId);
  if (!first || !last)
    throw Error("Choose both a starting point and an ending point.");
  if (!trip.places.every(resolved))
    throw Error("Confirm coordinates for every location before planning.");
  const stops = trip.places.filter(
    (p) => p.id !== trip.startId && p.id !== trip.endId,
  );
  if (stops.length > 20) throw Error("Use at most 20 intermediate stops.");
  if (new Set(trip.places.map((p) => p.id)).size !== trip.places.length)
    throw Error("The trip has duplicate locations.");
  const point = (p, id = p.id) => ({
    id,
    latitude: p.latitude,
    longitude: p.longitude,
  });
  let ordered = stops;
  if (manualOrder) {
    if (
      manualOrder.length !== stops.length ||
      new Set(manualOrder).size !== stops.length ||
      manualOrder.some((id) => !stops.some((p) => p.id === id))
    )
      throw Error("The stop order is invalid.");
    ordered = manualOrder.map((id) => stops.find((p) => p.id === id));
  }
  return {
    revision: trip.revision,
    start: point(first, "start"),
    end: point(last, "end"),
    stops: ordered.map((p) => point(p)),
    roadPolicy: { avoidTolls: false, avoidFerries: true, avoidUnpaved: true },
  };
}
export function validateReply(reply, request, manual = false) {
  const expected = request.stops.map((p) => p.id),
    ids = reply.orderedStopIds;
  if (
    reply.revision !== request.revision ||
    reply.status !== (manual ? "manual" : "optimized") ||
    !Array.isArray(ids) ||
    ids.length !== expected.length ||
    new Set(ids).size !== expected.length ||
    ids.some((id) => !expected.includes(id))
  )
    throw Error(
      "The server returned an inconsistent stop order. Please retry.",
    );
  if (manual && ids.some((id, i) => id !== expected[i]))
    throw Error("The server changed your manual order.");
  const legs = reply.legDistancesMeters;
  if (
    !Array.isArray(legs) ||
    legs.length !== expected.length + 1 ||
    legs.some((d) => !Number.isSafeInteger(d) || d < 0) ||
    !Number.isSafeInteger(reply.distanceMeters) ||
    reply.distanceMeters < 0 ||
    legs.reduce((a, b) => a + b, 0) !== reply.distanceMeters
  )
    throw Error("The server returned an invalid distance. Please retry.");
  const geometry = reply.geometry?.coordinates;
  const safeGeometry =
    Array.isArray(geometry) &&
    geometry.length <= 50000 &&
    geometry.every(
      (p) =>
        Array.isArray(p) &&
        p.length === 2 &&
        resolved({ latitude: p[1], longitude: p[0] }),
    )
      ? geometry
      : null;
  return {
    revision: reply.revision,
    order: ids,
    distance: reply.distanceMeters,
    legs,
    manual,
    stale: false,
    geometry: safeGeometry,
  };
}
export const currentResult = (trip, snapshot) =>
  !!trip && trip.id === snapshot.id && trip.revision === snapshot.revision;
export function move(order, index, delta) {
  const result = [...order],
    next = index + delta;
  if (index < 0 || index >= order.length || next < 0 || next >= order.length)
    return result;
  [result[index], result[next]] = [result[next], result[index]];
  return result;
}
export function validateSaved(value) {
  if (!Array.isArray(value)) throw Error("Saved trips must be a list.");
  const ids = new Set();
  for (const t of value) {
    if (
      !t ||
      typeof t.id !== "string" ||
      ids.has(t.id) ||
      typeof t.title !== "string" ||
      !Array.isArray(t.places) ||
      !Number.isSafeInteger(t.revision) ||
      t.revision < 0
    )
      throw Error("Saved trip data is invalid.");
    ids.add(t.id);
    if (
      t.places.some(
        (p) =>
          !p ||
          typeof p.id !== "string" ||
          typeof p.name !== "string" ||
          typeof p.address !== "string",
      ) ||
      new Set(t.places.map((p) => p.id)).size !== t.places.length
    )
      throw Error("Saved locations are invalid.");
    // Stored route results are not trusted as current; recalculate after importing/reloading.
    t.plan = null;
  }
  return value;
}
