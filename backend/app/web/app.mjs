import { mountRouteMap, removeRouteMap } from "./route-map.mjs?v=0.4.2";
import {
  uid,
  newTrip,
  resolved,
  coordinates,
  placeName,
  requestFor,
  validateReply,
  currentResult,
  move,
  validateSaved,
  arrivalPoint,
  arrivalDistance,
  failedPlaces,
} from "./core.mjs?v=0.4.2";
const ARROW =
  '<svg class="icon" aria-hidden="true" viewBox="0 0 16 16"><path d="M3 13L13 3M4 3h9v9" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
const TRASH = '<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const KEY = "trip-planner.web.v1",
  app = document.querySelector("#app"),
  dialog = document.querySelector("#editor"),
  form = document.querySelector("#place-form");
let trips = [],
  selected = null,
  view = "places",
  busy = null,
  storageBlocked = false,
  lastFailure = null,
  noticeTimer;
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const active = () => trips.find((t) => t.id === selected);
const distance = (value) =>
  new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(
    value / 1000,
  );
function notice(message, error = false) {
  const el = document.querySelector("#notice");
  el.textContent = message;
  el.className = `notice${error ? " error" : ""}`;
  el.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => (el.hidden = true), error ? 10000 : 5000);
}
try {
  trips = validateSaved(JSON.parse(localStorage.getItem(KEY) || "[]"));
} catch {
  storageBlocked = true;
  notice(
    "Saved trips could not be loaded. Export a backup before recovering browser storage. Existing data has not been overwritten.",
    true,
  );
}
function commit(next) {
  if (storageBlocked)
    throw Error(
      "Storage is unavailable or needs recovery. Export your saved data first.",
    );
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    throw Error(
      "Could not save changes. Browser storage may be full or disabled. Export a backup and retry.",
    );
  }
  trips = next;
}
function mutate(edit, { invalidate = true } = {}) {
  const next = structuredClone(trips),
    trip = next.find((t) => t.id === selected);
  if (!trip) throw Error("Choose a trip first.");
  edit(trip);
  if (invalidate) {
    trip.revision++;
    trip.plan = null;
  }
  commit(next);
  if (busy?.id === selected) {
    busy.controller.abort();
    busy = null;
  }
  lastFailure = null;
  render();
}
function storageTools() {
  return `<div class="storage"><button class="text-button" data-action="export">Export backup ↗</button><button class="text-button" data-action="import">Import backup ↗</button><input type="file" accept="application/json,.json" id="import-file" hidden></div>`;
}
function home() {
  return `<section class="intro"><div><span class="eyebrow">MAKE ROOM FOR THE JOURNEY</span><h1>A better order<br>to your day.</h1><p>Gather your places. Find a shorter drive.<br>Keep the freedom to change your mind.</p></div><aside><strong>One trip.<br>Every stop.</strong>Your places stay together, from the first idea to the final route.</aside></section><div class="grid"><section class="panel create-panel"><span class="eyebrow">START SOMETHING</span><h2>Where are you headed?</h2><p>Give your trip a title, then start collecting places.</p><form id="create-form"><label>Trip title<input name="title" required maxlength="120" placeholder="A day around Jerusalem" autocomplete="off"></label><button>Create a trip ↗</button></form></section><section><div class="section-head"><h2>Your trips</h2><span class="count">${trips.length} saved</span></div>${trips.length ? trips.map((t) => `<article class="trip-row"><button class="trip-card" data-trip="${esc(t.id)}"><h3 dir="auto">${esc(t.title)}</h3><small>${t.places.length} locations · ${t.places.filter((p) => !resolved(p)).length} need coordinates</small><span class="arrow" aria-hidden="true">↗</span></button><button class="trip-delete" data-action="delete-trip" data-delete-trip="${esc(t.id)}" aria-label="Delete ${esc(t.title)}" title="Delete trip">${TRASH}</button></article>`).join("") : `<div class="empty"><span class="empty-icon" aria-hidden="true">⌁</span><strong>Your next trip starts here.</strong><br>Create a trip and add the places you want to visit.<br><button class="text-button" data-action="sample">Try a sample Tel Aviv trip ↗</button></div>`}${storageTools()}<p class="footnote">Trips stay in this browser on this device. Export a backup to move them elsewhere. On iPhone, paste shared links into a location’s address field.</p></section></div>`;
}
function placeList(t) {
  return `<div class="editor-layout"><section class="panel"><div class="section-head"><h2>Your places</h2><button data-action="add">+ Add location</button></div>${t.places.length ? t.places.map((p, i) => `<article class="location"><span class="number">${i + 1}</span><div class="place-copy"><h3 dir="auto">${esc(p.name)}</h3><p dir="auto">${esc(p.address || `${p.latitude}, ${p.longitude}`)}</p><span class="badge ${resolved(p) ? "" : "pending"}">${resolved(p) ? "Coordinates confirmed" : "Needs coordinates"}</span>${p.id === t.startId ? '<span class="badge">Start</span>' : ""}${p.id === t.endId ? '<span class="badge">End</span>' : ""}</div><div class="actions"><button class="icon-button" data-edit="${esc(p.id)}" aria-label="Edit ${esc(p.name)}">Edit</button><button class="icon-button" data-remove="${esc(p.id)}" aria-label="Remove ${esc(p.name)}">×</button></div></article>`).join("") : `<div class="empty">A place for every stop.<br>Add your first location to get started.</div>`}</section><aside><div class="tip"><h3>Collect now. Plan later.</h3><p>Paste a Google Maps or Waze link, an address, or coordinates. Places save automatically when you tap Save.</p><p>Map links fill the name and coordinates automatically when available. You can edit them before saving.</p></div><button class="wide" data-view="plan" ${t.places.length ? "" : "disabled"}>${t.startId && t.endId ? "View saved route →" : "Choose start and end →"}</button><p class="footnote">Up to 20 intermediate stops, with separate start and end points.</p></aside></div>`;
}
function overview() {
  return `<section class="route-overview" aria-label="Route map"><div class="map-toolbar"><strong>Route map</strong><button type="button" id="fit-route" class="text-button">Show full route</button></div><div id="route-map" role="region" aria-label="Interactive street map with route and stops"></div><p class="map-legend">S · Start &nbsp; 1, 2… · Stops &nbsp; E · End</p><p id="map-status" role="status" aria-live="polite"></p><button type="button" id="reload-map" class="text-button">Reload map</button></section>`;
}
function routeList(t) {
  const p = t.plan;
  if (!p)
    return `<div class="empty"><span class="empty-icon" aria-hidden="true">⌁</span>Your route will appear here.<br>Select your endpoints and optimize your stops.</div>`;
  const start = t.places.find((x) => x.id === t.startId),
    end = t.places.find((x) => x.id === t.endId);
  return `<div class="result ${p.stale ? "stale" : ""}"><span class="eyebrow">${p.stale ? "ORDER CHANGED" : p.manual ? "YOUR CHOSEN ORDER" : "OPTIMIZED ROUTE"}</span>${p.stale ? '<div class="distance" style="font-size:26px;letter-spacing:-.6px">Recalculate distance</div><p>The previous distance no longer applies to this order.</p>' : `<div class="distance">${distance(p.distance)} <small>km</small></div><p>Approximate road distance. ${p.manual ? "Your order is preserved." : "A shorter visiting order may still exist."}</p>`}</div><div class="route-stop"><span class="number">↗</span><div class="place-copy"><span class="route-label">Start</span><h3 dir="auto">${esc(start?.name)}</h3></div></div>${p.order
    .map((id, i) => {
      const place = t.places.find((x) => x.id === id);
      return `<div class="route-stop"><span class="number">${i + 1}</span><div class="place-copy"><h3 dir="auto">${esc(place?.name)}</h3></div><div class="move-buttons"><button data-move="${i}" data-delta="-1" ${i === 0 || busy ? "disabled" : ""} aria-label="Move ${esc(place?.name)} earlier">↑</button><button data-move="${i}" data-delta="1" ${i === p.order.length - 1 || busy ? "disabled" : ""} aria-label="Move ${esc(place?.name)} later">↓</button></div></div>`;
    })
    .join(
      "",
    )}<div class="route-stop"><span class="number">●</span><div class="place-copy"><span class="route-label">End</span><h3 dir="auto">${esc(end?.name)}</h3></div></div>${!p.stale ? overview(p) : ""}`;
}
function planScreen(t) {
  const options = (chosen) =>
    `<option value="">Choose a location</option>${t.places.map((p) => `<option value="${esc(p.id)}" ${p.id === chosen ? "selected" : ""}>${esc(p.name)}</option>`).join("")}`;
  const unresolved = t.places.filter((p) => !resolved(p)).length;
  return `<div class="editor-layout plan-layout"><section class="panel"><div class="section-head"><h2>Your route</h2><span class="count">Distance, not duration</span></div>${routeList(t)}</section><aside class="panel"><span class="eyebrow">FIX THE ENDS. ARRANGE THE REST.</span><h2>Start & end</h2><details class="endpoint-editor" ${t.startId && t.endId ? "" : "open"}><summary>${t.startId && t.endId ? `Saved endpoints · Edit start & end` : "Choose start & end"}</summary><p class="help">Choose different endpoints, or the same place for a round trip.</p><label class="endpoint">Starting point<select id="start-select">${options(t.startId)}</select></label><label class="endpoint">Ending point<select id="end-select">${options(t.endId)}</select></label></details>${t.startId && t.endId ? `<p class="help" dir="auto"><strong>Start:</strong> ${esc(t.places.find(p=>p.id===t.startId)?.name)}<br><strong>End:</strong> ${esc(t.places.find(p=>p.id===t.endId)?.name)}</p>` : ""}${unresolved ? `<p class="field-error">${unresolved} locations need coordinates. <button class="text-button" data-view="places">Edit locations →</button></p>` : ""}<button class="wide" data-action="optimize" ${busy || unresolved || !t.startId || !t.endId ? "disabled" : ""}>${busy ? '<span class="busy"></span>Calculating…' : t.plan ? "Optimize again ↗" : "Optimize route ↗"}</button>${busy ? '<button class="text-button" data-action="cancel">Cancel calculation</button>' : ""}${t.plan?.stale ? '<button class="wide secondary" data-action="calculate" ' + (busy ? "disabled" : "") + ">Calculate my order</button>" : ""}${lastFailure ? '<button class="text-button retry" data-action="retry">Retry last calculation ↗</button>' : ""}<p class="help">Move stops with ↑ and ↓. Recalculate to update distance while keeping your order.</p><p class="footnote">Road data © OpenStreetMap contributors. Routing: Routino. Imported road data may differ from current access conditions.</p></aside></div>`;
}
function render() {
  removeRouteMap();
  const t = active();
  app.innerHTML = (
    t
      ? `<button class="text-button back" data-action="home">← All trips</button><div class="trip-heading"><div><span class="eyebrow">YOUR TRIP</span><h1 dir="auto">${esc(t.title)}</h1><p>${t.places.length} places, one plan.</p></div><button class="trip-delete" data-action="delete-trip" aria-label="Delete ${esc(t.title)}" title="Delete trip">${TRASH}</button></div><nav class="steps" aria-label="Trip planning"><button class="step ${view === "places" ? "active" : ""}" data-view="places"><span>1</span>Collect places</button><button class="step ${view === "plan" ? "active" : ""}" data-view="plan" ${t.places.length ? "" : "disabled"}><span>2</span>Plan your route</button></nav>${view === "plan" ? planScreen(t) : placeList(t)}`
      : home()
  ).replaceAll("↗", ARROW);
  if (!t) selected = null;
  if (t && view === "plan" && lastFailure?.code === "location_not_routable") {
    const ids = lastFailure.placeIds || [];
    const affected = t.places.filter(p => ids.includes(p.id));
    app.insertAdjacentHTML("beforeend", `<section class="panel arrival-recovery" aria-label="Arrival points"><div class="arrival-recovery-heading"><span class="eyebrow">LOCATION NEEDS ATTENTION</span><h2>Choose a reachable arrival point</h2><p role="alert">${affected.length ? "We couldn’t find a nearby driving road for the location below." : "We couldn’t identify the affected location. Retry the calculation or check your saved locations."}</p></div>${affected.map(p => `<article class="arrival-recovery-place"><h3 dir="auto">${esc(p.name)}</h3><p class="help">Your original destination stays saved. Choose a suitable entrance or parking area; access is unverified.</p>${p.arrival ? `<p class="arrival-adjustment">Arrival point adjusted · ${arrivalDistance(p)} m from destination</p>` : ""}<div class="arrival-recovery-actions"><button type="button" data-arrival="${esc(p.id)}" ${busy ? "disabled" : ""}>Choose arrival point</button><button type="button" class="secondary" data-edit="${esc(p.id)}">Edit location</button>${p.arrival ? `<button type="button" class="text-button" data-reset-arrival="${esc(p.id)}" ${busy ? "disabled" : ""}>Reset to original location</button>` : ""}</div></article>`).join("")}</section>`);
  }
  const recovery = app.querySelector(".arrival-recovery");
  if (recovery) app.querySelector(".plan-layout")?.before(recovery);
  bindForms();
  if (t && view === "plan") mountRouteMap(t);
}
function bindForms() {
  document.querySelector("#create-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    try {
      const t = newTrip(new FormData(e.target).get("title"));
      commit([t, ...trips]);
      selected = t.id;
      view = "places";
      render();
    } catch (error) {
      notice(error.message, true);
    }
  });
  for (const [id, key] of [
    ["start-select", "startId"],
    ["end-select", "endId"],
  ])
    document.getElementById(id)?.addEventListener("change", (e) => {
      try {
        mutate((t) => (t[key] = e.target.value));
      } catch (error) {
        notice(error.message, true);
      }
    });
  document
    .querySelector("#import-file")
    ?.addEventListener("change", importBackup);
}
function openEditor(id = null) {
  const p = active()?.places.find((p) => p.id === id);
  form.reset();
  for (const [key, value] of Object.entries(p || {})) {
    if (form.elements.namedItem(key))
      form.elements.namedItem(key).value = value ?? "";
  }
  document.querySelector("#editor-title").textContent = p
    ? "Edit location"
    : "Add a location";
  document.querySelector("#form-error").textContent = "";
  dialog.showModal();
  setTimeout(() => form.elements.address.focus(), 0);
}
async function calculate(manual = false) {
  if (busy) return;
  const snapshot = structuredClone(active());
  let request;
  try {
    request = requestFor(snapshot, manual ? snapshot.plan?.order : null);
  } catch (error) {
    notice(error.message, true);
    return;
  }
  const token = uid(),
    controller = new AbortController();
  busy = { id: snapshot.id, token, controller };
  lastFailure = null;
  render();
  const timer = setTimeout(() => controller.abort("timeout"), 90000);
  try {
    const url = new URL(
      `../v1/routes/${manual ? "calculate" : "optimize"}`,
      location.href,
    );
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: controller.signal,
    });
    if (!response.ok) {
      const details = await response.json().catch(() => ({}));
      const message =
        {
          422: "Some locations cannot form a car route. Confirm their positions.",
          429: "The routing service is busy. Please retry.",
          503: "The routing service is unavailable. Please retry shortly.",
          504: "The calculation timed out. Try fewer stops.",
        }[response.status] ||
        `The server could not calculate this route (HTTP ${response.status}).`;
      const error = Error(message);
      error.code = details.error?.code;
      error.placeIds = failedPlaces(snapshot, details.error?.locationIds);
      throw error;
    }
    const result = validateReply(await response.json(), request, manual);
    if (
      !currentResult(
        trips.find((t) => t.id === snapshot.id),
        snapshot,
      )
    )
      return;
    const next = structuredClone(trips),
      target = next.find((t) => t.id === snapshot.id);
    target.plan = result;
    commit(next);
    notice("Your route is ready.");
  } catch (error) {
    if (busy?.token !== token) return;
    lastFailure = { manual, code: error.code, placeIds: error.placeIds };
    notice(
      controller.signal.aborted
        ? controller.signal.reason === "timeout"
          ? "The request timed out. Your trip is saved; please retry."
          : "Calculation cancelled."
        : error.message ||
            "Could not reach the server. Check your connection and retry.",
      true,
    );
  } finally {
    clearTimeout(timer);
    if (busy?.token === token) busy = null;
    render();
  }
}
function exportBackup() {
  const raw = localStorage.getItem(KEY) || "[]";
  const blob = new Blob([raw], { type: "application/json" }),
    url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = "trip-planner-backup.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
async function importBackup(e) {
  try {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024)
      throw Error("Choose a backup smaller than 5 MB.");
    const next = validateSaved(JSON.parse(await file.text()));
    if (
      !confirm(
        "Replace the trips in this browser with this backup? Export your current trips first if you need them.",
      )
    )
      return;
    const previousBlocked = storageBlocked;
    storageBlocked = false;
    try {
      commit(next);
    } catch (error) {
      storageBlocked = previousBlocked;
      throw error;
    }
    selected = null;
    render();
    notice("Backup imported. Saved routes restored when valid.");
  } catch (error) {
    notice(error.message || "Could not import this backup.", true);
  }
}
app.addEventListener("click", (e) => {
  const button = e.target.closest("button");
  if (!button || button.disabled) return;
  try {
    if (button.dataset.trip) {
      selected = button.dataset.trip;
      view = active()?.startId && active()?.endId ? "plan" : "places";
      lastFailure = null;
      render();
      return;
    }
    if (button.dataset.view) {
      view = button.dataset.view;
      render();
      return;
    }
    if (button.dataset.edit) {
      openEditor(button.dataset.edit);
      return;
    }
    if (button.dataset.remove) {
      if (confirm("Remove this location from the trip?"))
        mutate((t) => {
          t.places = t.places.filter((p) => p.id !== button.dataset.remove);
          if (t.startId === button.dataset.remove) t.startId = "";
          if (t.endId === button.dataset.remove) t.endId = "";
        });
      return;
    }
    if (button.dataset.move !== undefined) {
      mutate(
        (t) => {
          t.revision++;
          t.plan = {
            ...t.plan,
            revision: t.revision,
            order: move(
              t.plan.order,
              Number(button.dataset.move),
              Number(button.dataset.delta),
            ),
            stale: true,
            distance: null,
            geometry: null,
          };
        },
        { invalidate: false },
      );
      return;
    }
    switch (button.dataset.action) {
      case "home":
        selected = null;
        render();
        break;
      case "add":
        openEditor();
        break;
      case "optimize":
        calculate(false);
        break;
      case "calculate":
        calculate(true);
        break;
      case "retry":
        calculate(lastFailure?.manual || false);
        break;
      case "cancel":
        busy?.controller.abort();
        break;
      case "export":
        exportBackup();
        break;
      case "import":
        document.querySelector("#import-file").click();
        break;
      case "delete-trip":
        { const id = button.dataset.deleteTrip || selected;
          const target = trips.find((t) => t.id === id);
          if (!target || !confirm(`Delete “${target.title}” and all its locations and saved route? This cannot be undone.`)) break;
          commit(trips.filter((t) => t.id !== id));
          if (busy?.id === id) { busy.controller.abort(); busy = null; }
          if (selected === id) selected = null;
          lastFailure = null;
          render();
          notice("Trip deleted.");
        }
        break;
      case "sample": {
        const t = newTrip("Tel Aviv afternoon");
        t.places = [
          {
            id: uid(),
            name: "Central Tel Aviv",
            address: "Sample coordinates",
            latitude: 32.08,
            longitude: 34.78,
          },
          {
            id: uid(),
            name: "Northern stop",
            address: "Sample coordinates",
            latitude: 32.083,
            longitude: 34.77,
          },
          {
            id: uid(),
            name: "Southern stop",
            address: "Sample coordinates",
            latitude: 32.06,
            longitude: 34.77,
          },
        ];
        t.startId = t.places[0].id;
        t.endId = t.places[2].id;
        commit([t, ...trips]);
        selected = t.id;
        view = "plan";
        render();
        break;
      }
    }
  } catch (error) {
    notice(error.message, true);
  }
});
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    if (!form.elements.latitude.value.trim() && !form.elements.longitude.value.trim()) {
      const ok = await extractPlace();
      if (!ok && /https?:\/\//.test(form.elements.address.value)) return;
    }
    const values = Object.fromEntries(new FormData(form)),
      has = values.latitude.trim() !== "" || values.longitude.trim() !== "";
    const place = {
      id: values.id || uid(),
      name: values.name.trim() || placeName(values.address, (trips.find((t) => t.id === selected)?.places.length || 0) + 1),
      address: values.address.trim(),
      latitude: has ? Number(values.latitude) : null,
      longitude: has ? Number(values.longitude) : null,
    };
    if (
      has &&
      (!values.latitude.trim() || !values.longitude.trim() || !resolved(place))
    )
      throw Error("Enter a valid latitude and longitude.");
    if (!has && !place.address)
      throw Error("Enter an address, link, or coordinates.");
    mutate((t) => {
      const index = t.places.findIndex((p) => p.id === place.id);
      if (index < 0) t.places.push(place);
      else {
        const previous = t.places[index];
        if (previous.latitude === place.latitude && previous.longitude === place.longitude && previous.arrival) place.arrival = previous.arrival;
        t.places[index] = place;
      }
    });
    dialog.close();
  } catch (error) {
    document.querySelector("#form-error").textContent = error.message;
  }
});
let extractionGeneration = 0;
let extractionController = null;
let extractionTimer;
let autoCoordinates = null;
let autoName = "";
async function extractPlace() {
  clearTimeout(extractionTimer);
  const generation = ++extractionGeneration;
  extractionController?.abort();
  extractionController = new AbortController();
  const source = form.elements.address.value.trim();
  const errorBox = document.querySelector("#form-error");
  let details = coordinates(source);
  const suggestedName = placeName(source, (trips.find((t) => t.id === selected)?.places.length || 0) + 1);
  if (!form.elements.name.value.trim() || form.elements.name.value === autoName) {
    form.elements.name.value = suggestedName;
    autoName = suggestedName;
  }
  if (!details && /https?:\/\//.test(source)) {
    errorBox.textContent = "Reading map link…";
    try {
      const response = await fetch(new URL("../v1/places/resolve", location.href), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: source }), signal: extractionController.signal,
      });
      const body = await response.json();
      if (!response.ok) throw Error(body.error?.message || "Could not read this link. Retry extraction.");
      if (!resolved(body)) throw Error("This link did not provide a destination position.");
      details = body;
    } catch (error) {
      if (generation === extractionGeneration && dialog.open && error.name !== "AbortError") errorBox.textContent = error.message;
      return false;
    }
  }
  if (generation !== extractionGeneration || !dialog.open || source !== form.elements.address.value.trim()) return false;
  if (details) {
    form.elements.latitude.value = details.latitude;
    form.elements.longitude.value = details.longitude;
    autoCoordinates = [String(details.latitude), String(details.longitude)];
    if (details.name && (!form.elements.name.value.trim() || form.elements.name.value === autoName)) {
      form.elements.name.value = details.name;
      autoName = details.name;
    }
    errorBox.textContent = "Map position extracted. You can save this place now.";
    return true;
  }
  errorBox.textContent = "";
  return false;
}
form.elements.address.addEventListener("input", () => {
  extractionGeneration++;
  extractionController?.abort();
  if (/https?:\/\//.test(form.elements.address.value) || (autoCoordinates && form.elements.latitude.value === autoCoordinates[0] && form.elements.longitude.value === autoCoordinates[1])) {
    form.elements.latitude.value = "";
    form.elements.longitude.value = "";
  }
  autoCoordinates = null;
  clearTimeout(extractionTimer);
  extractionTimer = setTimeout(extractPlace, 300);
});
dialog.addEventListener("close", () => {
  extractionGeneration++;
  extractionController?.abort();
  clearTimeout(extractionTimer);
  autoCoordinates = null;
  autoName = "";
});
document.querySelector("#extract").addEventListener("click", extractPlace);
document
  .querySelectorAll("[data-close]")
  .forEach((button) => button.addEventListener("click", () => dialog.close()));
document.querySelector(".brand").addEventListener("click", (e) => {
  e.preventDefault();
  selected = null;
  render();
});
window.addEventListener("storage", (e) => {
  if (e.key !== KEY) return;
  try {
    trips = validateSaved(JSON.parse(e.newValue || "[]"));
    if (busy) {
      busy.controller.abort();
      busy = null;
    }
    render();
    notice("Trips updated from another tab.");
  } catch {
    storageBlocked = true;
    notice(
      "Another tab changed saved data into an unreadable format. Export a backup before recovery.",
      true,
    );
  }
});
render();

function openArrival(id) {
  const trip = active(), place = trip?.places.find(p => p.id === id);
  if (!place || !resolved(place)) return notice("Confirm destination coordinates first.", true);
  const tripId = trip.id, target = arrivalPoint(place);
  const modal = document.createElement("dialog");
  modal.innerHTML = `<form><h2>Choose arrival point</h2><p>${esc(place.name)} — original destination stays saved.</p><p>Tap the map or drag the arrival pin. Access is unverified; choose a usable entrance or parking area.</p><div id="arrival-map" style="height:300px"></div><p id="arrival-map-status" role="status"></p><label>Arrival latitude<input name="lat" type="number" step="any" min="-90" max="90" required value="${target.latitude}"></label><label>Arrival longitude<input name="lon" type="number" step="any" min="-180" max="180" required value="${target.longitude}"></label><p id="arrival-distance" aria-live="polite"></p><p id="arrival-error" role="alert"></p><button type="button" id="arrival-cancel">Cancel</button><button type="submit">Use this arrival point</button></form>`;
  document.body.append(modal);
  modal.showModal();
  let arrivalMap = null, marker = null;
  const fields = modal.querySelector("form").elements;
  const read = () => ({latitude: Number(fields.lat.value), longitude: Number(fields.lon.value)});
  const update = () => {
    const point = read();
    modal.querySelector("#arrival-distance").textContent = fields.lat.value && fields.lon.value && resolved(point) ? `${arrivalDistance({...place, arrival:point})} m from original destination` : "Enter valid coordinates.";
    if (resolved(point)) marker?.setLatLng([point.latitude, point.longitude]);
  };
  modal.querySelector("#arrival-cancel").onclick = () => modal.close();
  modal.addEventListener("close", () => { arrivalMap?.remove(); modal.remove(); }, {once:true});
  if (globalThis.L) {
    const L = globalThis.L;
    arrivalMap = L.map(modal.querySelector("#arrival-map")).setView([target.latitude,target.longitude],16);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(arrivalMap).on("tileerror", () => {modal.querySelector("#arrival-map-status").textContent="Map tiles unavailable. You can enter arrival coordinates below.";});
    L.circleMarker([place.latitude,place.longitude],{color:"#a43",radius:8}).addTo(arrivalMap).bindTooltip("Original destination");
    marker = L.marker([target.latitude,target.longitude],{draggable:true,title:"Arrival point"}).addTo(arrivalMap);
    const choose = latlng => {fields.lat.value=latlng.lat.toFixed(6);fields.lon.value=latlng.lng.toFixed(6);update();};
    arrivalMap.on("click",e=>choose(e.latlng));
    marker.on("dragend",()=>choose(marker.getLatLng()));
  } else modal.querySelector("#arrival-map-status").textContent="Map unavailable. Enter arrival coordinates below.";
  fields.lat.oninput = fields.lon.oninput = update;
  update();
  modal.querySelector("form").onsubmit = e => {
    e.preventDefault();
    try {
      if (selected !== tripId) throw Error("The active trip changed. Reopen the arrival editor.");
      const point = read();
      if (!fields.lat.value || !fields.lon.value || !resolved(point)) throw Error("Enter valid arrival coordinates.");
      mutate(t => {t.places.find(p=>p.id===id).arrival=point;});
      modal.close();
      calculate(false);
    } catch(error) {modal.querySelector("#arrival-error").textContent=error.message;}
  };
}
app.addEventListener("click",e=>{
  const choose=e.target.closest("[data-arrival]"), reset=e.target.closest("[data-reset-arrival]");
  if (choose) openArrival(choose.dataset.arrival);
  if (reset) mutate(t=>{delete t.places.find(p=>p.id===reset.dataset.resetArrival).arrival;});
});
