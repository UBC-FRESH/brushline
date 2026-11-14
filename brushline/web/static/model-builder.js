const DEFAULT_SOURCES = ["lidarbc", "vri", "dra", "ften", "bec", "boundaries"];

const state = {
  aois: [],
  catalogue: null,
  session: null,
  selectedAoi: null,
  drawnGeometry: null,
  drawing: false,
  drawStart: null,
  sources: new Set(DEFAULT_SOURCES),
  connectors: new Set(),
};

const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
const stateClass = (value) => String(value ?? "unknown").replace(/[^a-z_]/g, "");
const fmt = (value) => Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 });

function setStatus(text, isError = false) {
  const node = $("status");
  node.textContent = text;
  node.style.background = isError ? "#f7dede" : "rgba(255,255,255,0.12)";
  node.style.color = isError ? "#8c2f2f" : "#fff";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (error) {
      // The status text is the safe fallback.
    }
    throw new Error(detail);
  }
  return response.json();
}

async function boot() {
  try {
    const [aois, catalogue] = await Promise.all([
      api("/api/model-builder/aois"),
      api("/api/model-builder/catalogue"),
    ]);
    state.aois = aois.aois;
    state.catalogue = catalogue;
    state.selectedAoi = state.aois[0] || null;
    fillSelect("asset-type", aois.asset_types, "transmission");
    fillSelect("standard", aois.standards, "clearance");
    renderAoiList();
    renderSources();
    renderConnectors();
    renderMap();
    setStatus("Catalogue loaded. Select an AOI to preview a plan.");
  } catch (error) {
    setStatus(`Could not load the prototype: ${error.message}`, true);
  }
}

function fillSelect(id, values, selected) {
  const select = $(id);
  select.innerHTML = "";
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value.replaceAll("_", " ");
    if (value === selected) option.selected = true;
    select.append(option);
  }
}

function renderAoiList() {
  const target = $("aoi-list");
  target.innerHTML = "";
  state.aois.forEach((aoi) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `aoi-button${state.selectedAoi?.id === aoi.id ? " active" : ""}`;
    button.innerHTML = `${esc(aoi.name)}<small>${esc(aoi.asset_type)} · ${esc(aoi.management_standard)}</small>`;
    button.addEventListener("click", () => {
      state.selectedAoi = aoi;
      state.drawnGeometry = null;
      renderAoiList();
      renderMap();
      $("map-note").textContent = "Synthetic fixture coverage. Missing sources stay visible in the gap panel.";
    });
    target.append(button);
  });
  if (state.selectedAoi?.id === "custom") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "aoi-button active";
    button.innerHTML = "Drawn AOI<small>custom rectangle · coverage missing</small>";
    target.append(button);
  }
}

function sourceAvailability(sourceId) {
  const rows = state.session?.availability || [];
  return rows.find((row) => row.source_id === sourceId);
}

function renderSources() {
  const target = $("source-list");
  target.innerHTML = "";
  const sources = state.catalogue?.sources || [];
  if (!sources.length) {
    target.innerHTML = '<p class="empty">No catalogue sources loaded.</p>';
    return;
  }
  sources.forEach((source) => {
    const availability = sourceAvailability(source.id);
    const row = document.createElement("label");
    row.className = "source-row";
    row.innerHTML = `
      <input type="checkbox" ${state.sources.has(source.id) ? "checked" : ""} data-source="${esc(source.id)}">
      <span>
        <span class="source-name">${esc(source.name)}</span>
        <span class="source-meta">${esc(source.provider)} · ${esc(source.licence)} · ${esc(source.access_status)}</span>
      </span>
      <span class="state state-${stateClass(availability?.coverage_state || source.access_status)}">
        ${esc(availability?.coverage_state || source.access_status)}
      </span>`;
    row.querySelector("input").addEventListener("change", (event) => {
      if (event.target.checked) state.sources.add(source.id);
      else state.sources.delete(source.id);
    });
    target.append(row);
  });
}

function renderConnectors() {
  const target = $("connector-list");
  target.innerHTML = "";
  const connectors = state.catalogue?.connectors || [];
  if (!connectors.length) {
    target.innerHTML = '<p class="empty">No private connectors loaded.</p>';
    return;
  }
  connectors.forEach((connector) => {
    const row = document.createElement("label");
    row.className = "source-row";
    row.innerHTML = `
      <input type="checkbox" ${state.connectors.has(connector.id) ? "checked" : ""} data-connector="${esc(connector.id)}">
      <span>
        <span class="source-name">${esc(connector.name)}</span>
        <span class="source-meta">${esc(connector.owner)} · ${esc(connector.classification)}</span>
      </span>
      <span class="state state-${connector.approved ? "observed" : "blocked"}">
        ${connector.approved ? "approved" : "approval needed"}
      </span>`;
    row.querySelector("input").addEventListener("change", (event) => {
      if (event.target.checked) state.connectors.add(connector.id);
      else state.connectors.delete(connector.id);
    });
    target.append(row);
  });
}

function geometryPoints(geometry) {
  if (!geometry || !Array.isArray(geometry.coordinates)) return [];
  if (geometry.type === "Polygon") {
    return (geometry.coordinates[0] || []).map((point) => point.slice(0, 2).join(",")).join(" ");
  }
  if (geometry.type === "MultiPolygon") {
    return (geometry.coordinates[0]?.[0] || []).map((point) => point.slice(0, 2).join(",")).join(" ");
  }
  return [];
}

function renderMap(preview = null) {
  const shapes = $("aoi-shapes");
  shapes.innerHTML = "";
  const geometry = state.drawnGeometry || state.selectedAoi?.geometry;
  if (geometry) {
    const polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    polygon.setAttribute("points", geometryPoints(geometry));
    polygon.setAttribute("fill", "rgba(31, 107, 79, 0.18)");
    polygon.setAttribute("stroke", "#1f6b4f");
    polygon.setAttribute("stroke-width", "3");
    shapes.append(polygon);
  }
  if (preview) {
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", Math.min(preview.x1, preview.x2));
    rect.setAttribute("y", Math.min(preview.y1, preview.y2));
    rect.setAttribute("width", Math.abs(preview.x2 - preview.x1));
    rect.setAttribute("height", Math.abs(preview.y2 - preview.y1));
    rect.setAttribute("fill", "rgba(35, 83, 109, 0.18)");
    rect.setAttribute("stroke", "#23536d");
    rect.setAttribute("stroke-dasharray", "6 4");
    shapes.append(rect);
  }
}

function mapPoint(event) {
  const rect = $("map").getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(600, ((event.clientX - rect.left) / rect.width) * 600)),
    y: Math.max(0, Math.min(200, ((event.clientY - rect.top) / rect.height) * 200)),
  };
}

function wireMapDrawing() {
  const map = $("map");
  map.addEventListener("pointerdown", (event) => {
    if (!state.drawing) return;
    state.drawStart = mapPoint(event);
    map.setPointerCapture(event.pointerId);
  });
  map.addEventListener("pointermove", (event) => {
    if (!state.drawing || !state.drawStart) return;
    const current = mapPoint(event);
    renderMap({
      x1: state.drawStart.x,
      y1: state.drawStart.y,
      x2: current.x,
      y2: current.y,
    });
  });
  map.addEventListener("pointerup", (event) => {
    if (!state.drawing || !state.drawStart) return;
    const end = mapPoint(event);
    const start = state.drawStart;
    state.drawStart = null;
    if (Math.abs(end.x - start.x) < 5 || Math.abs(end.y - start.y) < 5) return;
    const x1 = Math.min(start.x, end.x);
    const x2 = Math.max(start.x, end.x);
    const y1 = Math.min(start.y, end.y);
    const y2 = Math.max(start.y, end.y);
    state.drawnGeometry = {
      type: "Polygon",
      coordinates: [[[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]]],
    };
    state.selectedAoi = {
      id: "custom",
      name: "Drawn AOI",
      asset_type: $("asset-type").value,
      management_standard: $("standard").value,
      geometry: state.drawnGeometry,
      bbox: [x1, y1, x2, y2],
    };
    state.drawing = false;
    map.classList.remove("drawing");
    $("draw-toggle").textContent = "Draw AOI";
    renderAoiList();
    renderMap();
    $("map-note").textContent = "Drawn AOI. The prototype has no spatial coverage query, so every selected source is missing.";
  });
}

async function createSession() {
  try {
    if (!state.sources.size) throw new Error("Select at least one public source.");
    const payload = {
      asset_type: $("asset-type").value,
      management_standard: $("standard").value,
      horizon_years: Number($("horizon").value),
      currency: $("currency").value,
      source_ids: [...state.sources],
      connector_ids: [...state.connectors],
      bulk_fetch: $("bulk-fetch").checked,
      dry_run: true,
    };
    if (state.selectedAoi?.id === "custom" && state.drawnGeometry) {
      payload.geometry = state.drawnGeometry;
      payload.name = "Drawn AOI";
    } else {
      payload.aoi_id = state.selectedAoi?.id || "synthetic-corridor";
    }
    setStatus("Creating the plan-only preview...");
    state.session = await api("/api/model-builder/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderSession();
    setStatus(`Plan ${state.session.session_id} is ready. Review the gaps and approvals.`);
  } catch (error) {
    setStatus(`Plan failed: ${error.message}`, true);
  }
}

function renderSession() {
  const session = state.session;
  if (!session) return;
  renderSources();
  renderPlan(session.plan);
  renderGaps(session.gap);
  renderConnectorApprovals();
  $("approve-public").checked = session.public_approved;
  $("approve-bulk").checked = session.bulk_approved;
  if (session.review) renderReview(session.review);
}

function renderPlan(plan) {
  const target = $("plan");
  if (!plan?.items?.length) {
    target.innerHTML = '<p class="empty">No plan items. Select sources and create a plan.</p>';
    return;
  }
  const rows = plan.items.map((item) => `
    <tr>
      <td>${esc(item.kind)}<br><strong>${esc(item.reference_id)}</strong></td>
      <td>${esc(item.query)}</td>
      <td>${esc(item.licence)}</td>
      <td>${fmt(item.estimated_size_mb)} MB<br><span class="source-meta">${fmt(item.estimated_seconds)} s</span></td>
      <td><span class="state state-${stateClass(item.access_status)}">${esc(item.access_status)}</span></td>
      <td>${esc(item.materialization)}<br><span class="source-meta">${esc(item.materialization_pointer)}</span></td>
    </tr>`).join("");
  target.innerHTML = `
    <table>
      <thead><tr><th>Source</th><th>Query</th><th>Licence</th><th>Estimate</th><th>Access</th><th>Materialization</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="plan-total">${plan.items.length} items · ${fmt(plan.total_size_mb)} MB · ${fmt(plan.total_seconds)} s · mode ${esc(plan.mode)}</p>`;
}

function renderGaps(gap) {
  const target = $("gap-list");
  if (!gap?.gaps?.length) {
    target.innerHTML = '<p class="empty">No coverage gaps in the prototype fixture.</p>';
    return;
  }
  target.innerHTML = gap.gaps.map((item) => `
    <div class="gap-row ${item.decision === "stop" ? "" : "caveat"}">
      <strong>${esc(item.source_id)}</strong> · ${esc(item.state)} · ${esc(item.decision)}<br>
      ${esc(item.recommended_action)}
    </div>`).join("");
}

function renderConnectorApprovals() {
  const target = $("connector-approvals");
  const selected = state.session?.connector_ids || [];
  const approved = new Set(state.session?.approved_connectors || []);
  if (!selected.length) {
    target.innerHTML = '<p class="empty">No private connector selected.</p>';
    return;
  }
  target.innerHTML = selected.map((id) => {
    const connector = (state.catalogue?.connectors || []).find((item) => item.id === id);
    return `
      <label class="source-row">
        <input type="checkbox" data-approve-connector="${esc(id)}" ${approved.has(id) ? "checked" : ""}>
        <span><span class="source-name">${esc(connector?.name || id)}</span>
          <span class="source-meta">explicit private-connector approval</span></span>
        <span class="state state-${approved.has(id) ? "observed" : "blocked"}">${approved.has(id) ? "approved" : "blocked"}</span>
      </label>`;
  }).join("");
}

async function approveSession() {
  try {
    if (!state.session) throw new Error("Create a plan first.");
    const connectors = [...document.querySelectorAll("[data-approve-connector]")]
      .filter((input) => input.checked)
      .map((input) => input.dataset.approveConnector);
    state.session = await api(`/api/model-builder/sessions/${state.session.session_id}/approve`, {
      method: "POST",
      body: JSON.stringify({
        public_sources: $("approve-public").checked,
        bulk_fetch: $("approve-bulk").checked,
        connector_ids: connectors,
      }),
    });
    renderSession();
    setStatus(`Approvals saved. Session status: ${state.session.status}.`);
  } catch (error) {
    setStatus(`Approval failed: ${error.message}`, true);
  }
}

async function buildSession() {
  if (!state.session) {
    setStatus("Create a plan before building.", true);
    return;
  }
  $("progress").innerHTML = "";
  try {
    const result = await api(`/api/model-builder/sessions/${state.session.session_id}/build`, {
      method: "POST",
      body: JSON.stringify({ dry_run: $("dry-run").checked }),
    });
    state.session = result;
    renderSession();
    if (result.status === "blocked") {
      renderProgress(result.stages);
      setStatus("Build stopped. Read the failed stage and the gap report.", true);
      return;
    }
    streamProgress();
    setStatus(`Build ${result.status}. Loading the review...`);
  } catch (error) {
    setStatus(`Build failed: ${error.message}`, true);
  }
}

function renderProgress(stages) {
  const target = $("progress");
  target.innerHTML = stages.map((stage) => `
    <li class="${esc(stage.status)}">
      <strong>${esc(stage.name)}</strong> · ${esc(stage.status)}
      <div class="validator">validator: ${esc(stage.validator)}</div>
      <div>${esc(stage.detail)}</div>
    </li>`).join("");
}

function streamProgress() {
  const source = new EventSource(`/api/model-builder/sessions/${state.session.session_id}/progress`);
  const stages = [];
  source.addEventListener("stage", (event) => {
    stages.push(JSON.parse(event.data));
    renderProgress(stages);
  });
  source.addEventListener("done", async () => {
    source.close();
    try {
      state.session = await api(`/api/model-builder/sessions/${state.session.session_id}`);
      renderSession();
      renderProgress(state.session.stages);
      if (state.session.review) {
        renderReview(state.session.review);
        setStatus(`Review ready. ${state.session.review.open_questions.length} open questions.`);
      } else {
        setStatus(`Build ${state.session.status}. Review the failed stage.`, true);
      }
    } catch (error) {
      setStatus(`Progress stream closed: ${error.message}`, true);
    }
  });
  source.onerror = () => {
    source.close();
    if (state.session?.stages?.length) renderProgress(state.session.stages);
  };
}

function renderReview(review) {
  const target = $("review");
  if (!review) {
    target.innerHTML = '<p class="empty">Review appears after a completed dry run.</p>';
    return;
  }
  const distribution = Object.entries(review.state_distribution)
    .map(([key, value]) => `<li>${esc(key)}: <strong>${value}</strong></li>`)
    .join("") || "<li>No state rows.</li>";
  const gaps = review.gaps.length
    ? review.gaps.map((gap) => `<li>${esc(gap.source_id)} · ${esc(gap.state)} · ${esc(gap.recommended_action)}</li>`).join("")
    : "<li>No gaps.</li>";
  const questions = review.open_questions.map((item) => `<li>${esc(item)}</li>`).join("");
  const cards = review.model_cards.length
    ? review.model_cards.map((item) => `<li>${esc(item)}</li>`).join("")
    : "<li>No calibrated model cards in the synthetic fixture.</li>";
  target.innerHTML = `
    <div class="review-grid">
      <div class="metric"><strong>${review.segment_count}</strong><span>segments</span></div>
      <div class="metric"><strong>${review.coverage_counts.observed || 0}</strong><span>observed sources</span></div>
      <div class="metric"><strong>${review.coverage_counts.missing || 0}</strong><span>missing sources</span></div>
      <div class="metric"><strong>${review.gaps.length}</strong><span>gaps</span></div>
    </div>
    <h3>Initial state distribution</h3><ul>${distribution}</ul>
    <h3>Coverage and gaps</h3><ul>${gaps}</ul>
    <h3>Model cards</h3><ul>${cards}</ul>
    <h3>Open questions</h3><ul>${questions}</ul>
    <h3>Licences</h3><p>${review.licences.map(esc).join(", ") || "none"}</p>
    <h3>Provenance</h3><pre>${esc(JSON.stringify(review.provenance, null, 2))}</pre>
    <p class="source-meta">Source: ${esc(review.source)} · session ${esc(review.instance_id)}</p>`;
}

async function handoff() {
  try {
    if (!state.session) throw new Error("Create and complete a session first.");
    const record = await api(`/api/model-builder/sessions/${state.session.session_id}/handoff`, {
      method: "POST",
    });
    state.session.handoff = record;
    $("review").insertAdjacentHTML(
      "beforeend",
      `<p class="pill">Linked instance: ${esc(record.instance_root)} (dry run: ${record.dry_run})</p>`,
    );
    setStatus(`Handoff linked at ${record.instance_root}.`);
  } catch (error) {
    setStatus(`Handoff failed: ${error.message}`, true);
  }
}

$("draw-toggle").addEventListener("click", () => {
  state.drawing = !state.drawing;
  $("map").classList.toggle("drawing", state.drawing);
  $("draw-toggle").textContent = state.drawing ? "Cancel draw" : "Draw AOI";
  if (state.drawing) setStatus("Drag a rectangle on the map to draw a custom AOI.");
});
$("create-session").addEventListener("click", createSession);
$("approve").addEventListener("click", approveSession);
$("build").addEventListener("click", buildSession);
$("handoff").addEventListener("click", handoff);
wireMapDrawing();
boot();
