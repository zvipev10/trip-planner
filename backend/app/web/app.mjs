import {
  uid,
  newTrip,
  resolved,
  coordinates,
  requestFor,
  validateReply,
  currentResult,
  move,
  validateSaved,
} from "./core.mjs";
const ARROW =
  '<svg class="icon" aria-hidden="true" viewBox="0 0 16 16"><path d="M3 13L13 3M4 3h9v9" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
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
  return `<section class="intro"><div><span class="eyebrow">MAKE ROOM FOR THE JOURNEY</span><h1>A better order<br>to your day.</h1><p>Gather your places. Find a shorter drive.<br>Keep the freedom to change your mind.</p></div><aside><strong>One trip.<br>Every stop.</strong>Your places stay together, from the first idea to the final route.</aside></section><div class="grid"><section class="panel create-panel"><span class="eyebrow">START SOMETHING</span><h2>Where are you headed?</h2><p>Give your trip a title, then start collecting places.</p><form id="create-form"><label>Trip title<input name="title" required maxlength="120" placeholder="A day around Jerusalem" autocomplete="off"></label><button>Create a trip ↗</button></form></section><section><div class="section-head"><h2>Your trips</h2><span class="count">${trips.length} saved</span></div>${trips.length ? trips.map((t) => `<button class="trip-card" data-trip="${esc(t.id)}"><h3 dir="auto">${esc(t.title)}</h3><small>${t.places.length} locations · ${t.places.filter((p) => !resolved(p)).length} need coordinates</small><span class="arrow" aria-hidden="true">↗</span></button>`).join("") : `<div class="empty"><span class="empty-icon" aria-hidden="true">⌁</span><strong>Your next trip starts here.</strong><br>Create a trip and add the places you want to visit.<br><button class="text-button" data-action="sample">Try a sample Tel Aviv trip ↗</button></div>`}${storageTools()}<p class="footnote">Trips stay in this browser on this device. Export a backup to move them elsewhere. On iPhone, paste shared links into a location’s address field.</p></section></div>`;
}
function placeList(t) {
  return `<div class="editor-layout"><section class="panel"><div class="section-head"><h2>Your places</h2><button data-action="add">+ Add location</button></div>${t.places.length ? t.places.map((p, i) => `<article class="location"><span class="number">${i + 1}</span><div class="place-copy"><h3 dir="auto">${esc(p.name)}</h3><p dir="auto">${esc(p.address || `${p.latitude}, ${p.longitude}`)}</p><span class="badge ${resolved(p) ? "" : "pending"}">${resolved(p) ? "Coordinates confirmed" : "Needs coordinates"}</span>${p.id === t.startId ? '<span class="badge">Start</span>' : ""}${p.id === t.endId ? '<span class="badge">End</span>' : ""}</div><div class="actions"><button class="icon-button" data-edit="${esc(p.id)}" aria-label="Edit ${esc(p.name)}">Edit</button><button class="icon-button" data-remove="${esc(p.id)}" aria-label="Remove ${esc(p.name)}">×</button></div></article>`).join("") : `<div class="empty">A place for every stop.<br>Add your first location to get started.</div>`}</section><aside><div class="tip"><h3>Collect now. Plan later.</h3><p>Paste a Google Maps or Waze link, an address, or coordinates. Places save automatically when you tap Save.</p><p>Confirm each place’s latitude and longitude before calculating a route.</p></div><button class="wide" data-view="plan" ${t.places.length ? "" : "disabled"}>Choose start and end →</button><p class="footnote">Up to 20 intermediate stops, with separate start and end points.</p></aside></div>`;
}
function overview(plan) {
  const points = plan?.geometry;
  if (!Array.isArray(points) || points.length < 2) return "";
  const xs = points.map((p) => p[0]),
    ys = points.map((p) => p[1]),
    minx = Math.min(...xs),
    maxx = Math.max(...xs),
    miny = Math.min(...ys),
    maxy = Math.max(...ys),
    sx = maxx - minx || 0.001,
    sy = maxy - miny || 0.001;
  const map = (p) => [
    12 + ((p[0] - minx) / sx) * 276,
    128 - ((p[1] - miny) / sy) * 116,
  ];
  const step = Math.max(1, Math.ceil(points.length / 3000)),
    sample = points.filter((_, i) => i % step === 0);
  sample.push(points.at(-1));
  const path = sample
      .map(
        (p, i) =>
          `${i ? "L" : "M"}${map(p)
            .map((n) => n.toFixed(2))
            .join(",")}`,
      )
      .join(" "),
    first = map(points[0]),
    last = map(points.at(-1));
  return `<div class="route-overview"><span class="eyebrow">ROAD GEOMETRY · NOT A BASE MAP</span><svg viewBox="0 0 300 140" role="img" aria-label="Overview of the calculated road route"><path d="${path}" fill="none" stroke="#3d7b5e" stroke-width="2.5" stroke-linecap="round"/><circle cx="${first[0]}" cy="${first[1]}" r="5" fill="#173b32"/><circle cx="${last[0]}" cy="${last[1]}" r="5" fill="#b0ba72" stroke="#173b32"/></svg></div>`;
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
  return `<div class="editor-layout plan-layout"><section class="panel"><div class="section-head"><h2>Your route</h2><span class="count">Distance, not duration</span></div>${routeList(t)}</section><aside class="panel"><span class="eyebrow">FIX THE ENDS. ARRANGE THE REST.</span><h2>Start & end</h2><p class="help">Choose different endpoints, or the same place for a round trip.</p><label class="endpoint">Starting point<select id="start-select">${options(t.startId)}</select></label><label class="endpoint">Ending point<select id="end-select">${options(t.endId)}</select></label>${unresolved ? `<p class="field-error">${unresolved} locations need coordinates. <button class="text-button" data-view="places">Edit locations →</button></p>` : ""}<button class="wide" data-action="optimize" ${busy || unresolved || !t.startId || !t.endId ? "disabled" : ""}>${busy ? '<span class="busy"></span>Calculating…' : t.plan ? "Optimize again ↗" : "Optimize route ↗"}</button>${busy ? '<button class="text-button" data-action="cancel">Cancel calculation</button>' : ""}${t.plan?.stale ? '<button class="wide secondary" data-action="calculate" ' + (busy ? "disabled" : "") + ">Calculate my order</button>" : ""}${lastFailure ? '<button class="text-button retry" data-action="retry">Retry last calculation ↗</button>' : ""}<p class="help">Move stops with ↑ and ↓. Recalculate to update distance while keeping your order.</p><p class="footnote">Road data © OpenStreetMap contributors. Routing: Routino. Imported road data may differ from current access conditions.</p></aside></div>`;
}
function render() {
  const t = active();
  app.innerHTML = (
    t
      ? `<button class="text-button back" data-action="home">← All trips</button><div class="trip-heading"><div><span class="eyebrow">YOUR TRIP</span><h1 dir="auto">${esc(t.title)}</h1><p>${t.places.length} places, one plan.</p></div><button class="text-button danger" data-action="delete-trip">Delete trip</button></div><nav class="steps" aria-label="Trip planning"><button class="step ${view === "places" ? "active" : ""}" data-view="places"><span>1</span>Collect places</button><button class="step ${view === "plan" ? "active" : ""}" data-view="plan" ${t.places.length ? "" : "disabled"}><span>2</span>Plan your route</button></nav>${view === "plan" ? planScreen(t) : placeList(t)}`
      : home()
  ).replaceAll("↗", ARROW);
  if (!t) selected = null;
  bindForms();
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
  setTimeout(() => form.elements.name.focus(), 0);
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
      const message =
        {
          422: "Some locations cannot form a car route. Confirm their positions.",
          429: "The routing service is busy. Please retry.",
          503: "The routing service is unavailable. Please retry shortly.",
          504: "The calculation timed out. Try fewer stops.",
        }[response.status] ||
        `The server could not calculate this route (HTTP ${response.status}).`;
      throw Error(message);
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
    lastFailure = { manual };
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
    notice("Backup imported. Recalculate any routes.");
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
      view = "places";
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
        if (confirm("Delete this trip and its saved locations?")) {
          if (busy?.id === selected) {
            busy.controller.abort();
            busy = null;
          }
          commit(trips.filter((t) => t.id !== selected));
          selected = null;
          render();
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
form.addEventListener("submit", (e) => {
  e.preventDefault();
  try {
    const values = Object.fromEntries(new FormData(form)),
      has = values.latitude.trim() !== "" || values.longitude.trim() !== "";
    if (!values.name.trim()) throw Error("Enter a place name.");
    const place = {
      id: values.id || uid(),
      name: values.name.trim(),
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
      else t.places[index] = place;
    });
    dialog.close();
  } catch (error) {
    document.querySelector("#form-error").textContent = error.message;
  }
});
document.querySelector("#extract").addEventListener("click", () => {
  const p = coordinates(form.elements.address.value);
  if (p) {
    form.elements.latitude.value = p.latitude;
    form.elements.longitude.value = p.longitude;
    document.querySelector("#form-error").textContent =
      "Coordinates extracted. Please confirm the destination.";
  } else
    document.querySelector("#form-error").textContent =
      "No explicit coordinates found. Paste a longer link or enter coordinates manually.";
});
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
