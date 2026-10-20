import { arrivalPoint } from "./core.mjs?v=0.4.1";
let map = null;

export function removeRouteMap() {
  map?.remove();
  map = null;
}

export function mountRouteMap(trip) {
  const container = document.getElementById("route-map");
  if (!container || !trip?.plan || trip.plan.stale) return;
  const status = document.getElementById("map-status");
  const L = globalThis.L;
  if (!L) {
    status.textContent = "Map could not load. Reload this page to retry.";
    return;
  }
  map = L.map(container, { scrollWheelZoom: false, tapHold: true });
  const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
  }).addTo(map);
  tiles.on("tileerror", () => { status.textContent = "Street tiles could not load. Check your connection and tap Reload map."; });
  tiles.on("tileload", () => { status.textContent = ""; });
  const geometry = trip.plan.geometry || [];
  const bounds = geometry.map(([lon, lat]) => [lat, lon]);
  if (bounds.length >= 2) L.polyline(bounds, { color: "#146b58", weight: 5, opacity: 0.9 }).addTo(map);
  const find = (id) => trip.places.find((p) => p.id === id);
  const start = find(trip.startId), end = find(trip.endId);
  const roundTrip = start && end && start.latitude === end.latitude && start.longitude === end.longitude;
  const stops = [
    { place: start, label: roundTrip ? "S/E" : "S", role: roundTrip ? "Start and end" : "Start", kind: "start" },
    ...trip.plan.order.map((id, i) => ({ place: find(id), label: String(i + 1), role: `Stop ${i + 1}`, kind: "stop" })),
    ...(!roundTrip ? [{ place: end, label: "E", role: "End", kind: "end" }] : []),
  ];
  for (const { place, label, role, kind } of stops) {
    if (!place || !Number.isFinite(place.latitude) || !Number.isFinite(place.longitude)) continue;
    const target = arrivalPoint(place);
    const position = [target.latitude, target.longitude];
    bounds.push(position);
    const popup = document.createElement("div");
    popup.dir = "auto";
    popup.textContent = `${role}: ${place.name}`;
    const marker = L.marker(position, {
      title: `${role}: ${place.name}`, alt: `${role}: ${place.name}`,
      icon: L.divIcon({ className: `map-pin ${kind}`, html: `<span>${label}</span>`, iconSize: [34, 34], iconAnchor: [17, 17] }),
    }).addTo(map).bindPopup(popup);
    marker.getElement()?.setAttribute("aria-label", `${role}: ${place.name}`);
  }
  const fit = () => {
    map?.invalidateSize();
    if (bounds.length) map?.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 });
  };
  fit();
  document.getElementById("fit-route").onclick = fit;
  document.getElementById("reload-map").onclick = () => { status.textContent = "Loading street map…"; tiles.redraw(); };
}
