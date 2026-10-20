import test from "node:test";
import assert from "node:assert/strict";
import {
  newTrip,
  uid,
  coordinates,
  placeName,
  requestFor,
  validateReply,
  currentResult,
  move,
  validateSaved,
} from "../../app/web/core.mjs";
const place = (id, lat = 32, lon = 35) => ({
  id,
  name: id,
  address: "",
  latitude: lat,
  longitude: lon,
});
const sample = () => ({
  ...newTrip("Example"),
  places: [place("a"), place("b"), place("c")],
  startId: "a",
  endId: "c",
});
test("title precedes location collection", () => {
  assert.throws(() => newTrip(" "));
  assert.equal(newTrip(" Weekend ").title, "Weekend");
});
test("HTTP-compatible UUID fallback", () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  try {
    Object.defineProperty(globalThis, "crypto", {
      configurable: true,
      value: {
        getRandomValues: (b) => {
          b.fill(9);
          return b;
        },
      },
    });
    assert.match(
      uid(),
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  } finally {
    if (original) Object.defineProperty(globalThis, "crypto", original);
    else delete globalThis.crypto;
  }
});
test("separate endpoints are excluded from intermediate stops", () => {
  const r = requestFor(sample());
  assert.deepEqual(
    r.stops.map((p) => p.id),
    ["b"],
  );
  assert.equal(r.start.id, "start");
  assert.equal(r.end.id, "end");
});
test("round trip uses distinct endpoint roles and visits other places once", () => {
  const t = sample();
  t.endId = "a";
  const r = requestFor(t);
  assert.notEqual(r.start.id, r.end.id);
  assert.deepEqual(
    r.stops.map((p) => p.id),
    ["b", "c"],
  );
});
test("unresolved coordinates and missing endpoints block routing", () => {
  let t = sample();
  t.startId = "";
  assert.throws(() => requestFor(t));
  t = sample();
  t.places[1].latitude = null;
  assert.throws(() => requestFor(t));
});
test("twenty intermediate stops are supported; twenty-one are rejected", () => {
  const t = sample();
  t.places = Array.from({ length: 22 }, (_, i) => place(String(i)));
  t.startId = "0";
  t.endId = "21";
  assert.equal(requestFor(t).stops.length, 20);
  t.places.push(place("extra"));
  assert.throws(() => requestFor(t));
});
test("manual order must preserve every stop exactly once", () => {
  const t = sample();
  t.endId = "a";
  assert.deepEqual(
    requestFor(t, ["c", "b"]).stops.map((p) => p.id),
    ["c", "b"],
  );
  assert.throws(() => requestFor(t, ["b", "b"]));
});
test("reply validation rejects stale, missing, duplicate and negative results", () => {
  const r = requestFor(sample());
  const good = {
    revision: r.revision,
    orderedStopIds: ["b"],
    distanceMeters: 120,
    legDistancesMeters: [50, 70],
    status: "optimized",
  };
  assert.equal(validateReply(good, r).distance, 120);
  for (const bad of [
    { ...good, revision: 99 },
    { ...good, orderedStopIds: [] },
    { ...good, orderedStopIds: ["b", "b"] },
    { ...good, distanceMeters: -1 },
    { ...good, legDistancesMeters: [20, 30] },
  ])
    assert.throws(() => validateReply(bad, r));
});
test("manual calculation rejects reordered response", () => {
  const t = sample();
  t.endId = "a";
  const r = requestFor(t, ["c", "b"]);
  assert.throws(() =>
    validateReply(
      {
        revision: 0,
        orderedStopIds: ["b", "c"],
        distanceMeters: 3,
        legDistancesMeters: [1, 1, 1],
        status: "manual",
      },
      r,
      true,
    ),
  );
});
test("editing a trip invalidates an in-flight response", () => {
  const t = sample(),
    snapshot = structuredClone(t);
  assert.equal(currentResult(t, snapshot), true);
  t.revision++;
  assert.equal(currentResult(t, snapshot), false);
});
test("manual moving keeps endpoints out of the ordering operation", () => {
  assert.deepEqual(move(["b", "c", "d"], 0, 1), ["c", "b", "d"]);
  assert.deepEqual(move(["b", "c"], 0, -1), ["b", "c"]);
});
test("shared coordinate links resolve but camera positions and short links do not", () => {
  assert.deepEqual(coordinates("https://waze.com/ul?ll=32.08%2C34.78"), {
    latitude: 32.08,
    longitude: 34.78,
  });
  assert.equal(coordinates("https://maps.google.com/maps/@32,35,15z"), null);
  assert.equal(coordinates("https://maps.app.goo.gl/example"), null);
  assert.equal(coordinates("91,35"), null);
  assert.equal(coordinates(" ,35"), null);
});
test("backups reject malformed storage and clear unverified cached routes", () => {
  assert.throws(() => validateSaved({}));
  const t = sample();
  t.plan = { distance: 999 };
  assert.equal(validateSaved([t])[0].plan, null);
  assert.throws(() => validateSaved([sample(), { id: 1 }]));
});

test("Google destination data extracts actual place, ignoring camera position", () => {
  assert.deepEqual(coordinates("https://www.google.com/maps/place/Cafe+Five/@31,35,15z/data=!3d32.08!4d34.78"), { latitude: 32.08, longitude: 34.78 });
});
test("Waze geohash links decode the shared destination", () => {
  const result = coordinates("https://waze.com/ul/hsv8wrqkp9");
  assert.ok(result && result.latitude > 29 && result.latitude < 34 && result.longitude > 34 && result.longitude < 36);
});

test("names are extracted when available, with numbered fallbacks", () => {
  assert.equal(placeName("https://google.com/maps/place/Cafe+Five/data=!3d32!4d34"), "Cafe Five");
  assert.equal(placeName("https://waze.com/ul?ll=32,34", 5), "Place 5");
  assert.equal(placeName("https://google.com/maps?q=Coffee+Shop"), "Coffee Shop");
});

test("arrival override preserves original destination and applies to both round-trip endpoints", async () => {
  const {arrivalDistance, failedPlaces} = await import("../../app/web/core.mjs");
  const t=sample(); t.endId=t.startId;
  t.places[0].arrival={latitude:32.001,longitude:35.001};
  const r=requestFor(t);
  assert.equal(t.places[0].latitude,32);
  assert.equal(r.start.latitude,32.001);
  assert.equal(r.end.latitude,32.001);
  assert.notEqual(r.start.id,r.end.id);
  assert.ok(arrivalDistance(t.places[0])>100);
  assert.deepEqual(failedPlaces(t,["start","end","b","missing"]),["a","b"]);
  const restored=validateSaved(JSON.parse(JSON.stringify([t])))[0];
  assert.equal(restored.places[0].arrival.latitude,32.001);
  delete restored.places[0].arrival;
  assert.equal(requestFor(restored).start.latitude,32);
});

test("invalid imported arrival coordinates are rejected", () => {
  const t=sample();t.places[0].arrival={latitude:100,longitude:35};
  assert.throws(()=>validateSaved([t]),/arrival/);
  assert.throws(()=>requestFor(t),/arrival/);
});
