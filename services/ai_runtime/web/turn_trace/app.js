const STORAGE_KEYS = {
  clientId: "ai_runtime_turn_trace_client_id",
  internalToken: "ai_runtime_turn_trace_internal_token",
};

const state = {
  tokenRequired: false,
  traceEnabled: true,
  clients: [],
  clientId: "",
  sessionId: "",
  turn: null,
  sessions: [],
  turns: [],
  trace: null,
};

const API_PREFIX = window.location.pathname.replace(/\/debug\/turn-trace\/$/, "");

const els = {
  clientId: document.getElementById("clientId"),
  internalToken: document.getElementById("internalToken"),
  loadSessions: document.getElementById("loadSessions"),
  deleteSession: document.getElementById("deleteSession"),
  expandDetail: document.getElementById("expandDetail"),
  statusBanner: document.getElementById("statusBanner"),
  clientsMeta: document.getElementById("clientsMeta"),
  clientsList: document.getElementById("clientsList"),
  sessionsList: document.getElementById("sessionsList"),
  turnsList: document.getElementById("turnsList"),
  eventsList: document.getElementById("eventsList"),
  eventDetail: document.getElementById("eventDetail"),
  sessionsMeta: document.getElementById("sessionsMeta"),
  turnsMeta: document.getElementById("turnsMeta"),
  detailMeta: document.getElementById("detailMeta"),
  turnSummary: document.getElementById("turnSummary"),
  detailModal: document.getElementById("detailModal"),
  detailModalMeta: document.getElementById("detailModalMeta"),
  detailModalContent: document.getElementById("detailModalContent"),
  closeDetailModal: document.getElementById("closeDetailModal"),
};

function authHeaders() {
  const token = els.internalToken.value.trim();
  return token ? { "X-Internal-Token": token } : {};
}

async function fetchJson(url, { method = "GET", requireAuth = false } = {}) {
  const response = await fetch(url, {
    method,
    headers: authHeaders(),
  });
  if (!response.ok) {
    const text = await response.text();
    if (response.status === 401 && requireAuth) {
      throw new Error("Este entorno requiere INTERNAL_API_TOKEN para leer las trazas.");
    }
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function badge(kind) {
  return `<span class="badge badge-${escapeHtml(kind)}">${escapeHtml(kind)}</span>`;
}

function setStatus(message, kind = "info") {
  els.statusBanner.className = `status-banner status-${kind}`;
  els.statusBanner.textContent = message;
}

function updateSessionActions() {
  els.deleteSession.disabled = !state.clientId || !state.sessionId;
}

function updateDetailActions() {
  els.expandDetail.disabled = !state.trace;
}

function isDetailModalOpen() {
  return !els.detailModal.classList.contains("hidden");
}

function setEventDetailContent(text) {
  els.eventDetail.textContent = text;
  els.detailModalContent.textContent = text;
  els.detailModalMeta.textContent = els.detailMeta.textContent;
}

function openDetailModal() {
  if (!state.trace) {
    setStatus("Selecciona un turno antes de ampliar el detalle.", "warn");
    return;
  }
  els.detailModal.classList.remove("hidden");
  els.detailModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeDetailModal() {
  els.detailModal.classList.add("hidden");
  els.detailModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

function persistFormState() {
  localStorage.setItem(STORAGE_KEYS.clientId, els.clientId.value.trim());
  localStorage.setItem(STORAGE_KEYS.internalToken, els.internalToken.value.trim());
}

function restoreFormState() {
  const params = new URLSearchParams(window.location.search);
  els.clientId.value = params.get("client_id") || localStorage.getItem(STORAGE_KEYS.clientId) || "";
  els.internalToken.value = localStorage.getItem(STORAGE_KEYS.internalToken) || "";
  state.clientId = els.clientId.value.trim();
}

function renderClients() {
  els.clientsMeta.textContent = `${state.clients.length} clients`;
  if (!state.clients.length) {
    els.clientsList.innerHTML = `<div class="empty">Todavia no hay clients detectados con turn traces.</div>`;
    return;
  }

  els.clientsList.innerHTML = state.clients
    .map(
      (client) => `
        <button class="client-chip ${client.client_id === state.clientId ? "selected" : ""}" data-client-id="${escapeHtml(client.client_id)}">
          <strong>${escapeHtml(client.client_id)}</strong>
          <span>${escapeHtml(client.vertical || "-")} · ${escapeHtml(client.bridge || "-")}</span>
          <span>sesiones: ${escapeHtml(client.session_count || 0)}</span>
        </button>
      `
    )
    .join("");

  els.clientsList.querySelectorAll("[data-client-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.clientId = button.dataset.clientId;
      els.clientId.value = state.clientId;
      persistFormState();
      renderClients();
      await loadSessions();
    });
  });
}

function renderSessions() {
  els.sessionsMeta.textContent = `${state.sessions.length} sesiones`;
  updateSessionActions();
  if (!state.sessions.length) {
    els.sessionsList.innerHTML = `<div class="empty">No hay sesiones para este client_id.</div>`;
    return;
  }
  els.sessionsList.innerHTML = state.sessions
    .map(
      (session) => `
        <button class="list-item ${session.session_id === state.sessionId ? "selected" : ""}" data-session="${escapeHtml(session.session_id)}">
          <strong>${escapeHtml(session.session_id)}</strong>
          <span>${escapeHtml(session.vertical || "-")} · ${escapeHtml(session.bridge || "-")}</span>
          <span>${escapeHtml(session.latest_user_message || "-")}</span>
          <span>turnos: ${escapeHtml(session.turn_count || 0)}</span>
        </button>
      `
    )
    .join("");

  els.sessionsList.querySelectorAll("[data-session]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.sessionId = button.dataset.session;
      state.turn = null;
      state.trace = null;
      renderSessions();
      await loadTurns();
    });
  });
}

function renderTurns() {
  els.turnsMeta.textContent = state.sessionId ? `${state.turns.length} turnos en ${state.sessionId}` : "";
  if (!state.sessionId) {
    els.turnsList.innerHTML = `<div class="empty">Selecciona una sesion.</div>`;
    return;
  }
  if (!state.turns.length) {
    els.turnsList.innerHTML = `<div class="empty">Esta sesion todavia no tiene turn traces.</div>`;
    return;
  }
  els.turnsList.innerHTML = state.turns
    .map(
      (turn) => `
        <button class="list-item ${Number(turn.turn) === Number(state.turn) ? "selected" : ""}" data-turn="${escapeHtml(turn.turn)}">
          <strong>Turno ${escapeHtml(turn.turn)}</strong>
          <span>${badge(turn.status || "unknown")}</span>
          <span>${escapeHtml(turn.user_message || "-")}</span>
          <span>eventos: ${escapeHtml(turn.event_count || 0)}</span>
        </button>
      `
    )
    .join("");

  els.turnsList.querySelectorAll("[data-turn]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.turn = Number(button.dataset.turn);
      renderTurns();
      await loadTurnDetail();
    });
  });
}

function renderTrace() {
  updateDetailActions();
  if (!state.trace) {
    els.detailMeta.textContent = "";
    els.turnSummary.className = "summary-card empty";
    els.turnSummary.textContent = "Selecciona un turno para ver la traza.";
    els.eventsList.innerHTML = "";
    setEventDetailContent("Sin evento seleccionado.");
    return;
  }

  els.detailMeta.textContent = `turno ${state.trace.turn} · trace ${state.trace.trace_id}`;
  els.detailModalMeta.textContent = els.detailMeta.textContent;
  els.turnSummary.className = "summary-card";
  els.turnSummary.innerHTML = `
    <div><strong>Estado:</strong> ${badge(state.trace.status || "unknown")}</div>
    <div><strong>Client:</strong> ${escapeHtml(state.trace.client_id || "-")}</div>
    <div><strong>Mensaje:</strong> ${escapeHtml(state.trace.user_message || "-")}</div>
    <div><strong>Vertical:</strong> ${escapeHtml(state.trace.vertical || "-")}</div>
    <div><strong>Bridge:</strong> ${escapeHtml(state.trace.bridge || "-")}</div>
    <div><strong>Inicio:</strong> ${escapeHtml(state.trace.started_at || "-")}</div>
    <div><strong>Fin:</strong> ${escapeHtml(state.trace.ended_at || "-")}</div>
    <div><strong>Respuesta:</strong> ${escapeHtml((state.trace.response_payload || {}).answer || "-")}</div>
  `;

  const events = state.trace.events || [];
  els.eventsList.innerHTML = events
    .map(
      (event, index) => `
        <button class="event-item" data-index="${index}">
          ${badge(event.kind || "event")}
          <strong>${escapeHtml(event.name || "-")}</strong>
          <span>${escapeHtml(event.timestamp || "-")}</span>
        </button>
      `
    )
    .join("");

  els.eventsList.querySelectorAll("[data-index]").forEach((button) => {
    button.addEventListener("click", () => {
      const event = events[Number(button.dataset.index)];
      els.eventsList.querySelectorAll(".event-item").forEach((item) => item.classList.remove("selected"));
      button.classList.add("selected");
      setEventDetailContent(JSON.stringify(event, null, 2));
    });
  });

  if (events.length) {
    els.eventsList.querySelector("[data-index='0']")?.click();
  } else {
    setEventDetailContent("Este turno no tiene eventos registrados.");
  }
  updateDetailActions();
}

async function loadConfig() {
  const payload = await fetchJson(`${API_PREFIX}/debug/turn-traces/config`);
  state.traceEnabled = Boolean(payload.trace_enabled);
  state.tokenRequired = Boolean(payload.token_required);

  if (!state.traceEnabled) {
    setStatus("Turn trace esta deshabilitado en este runtime.", "warn");
    return;
  }

  if (state.tokenRequired && !els.internalToken.value.trim()) {
    setStatus("Este entorno requiere INTERNAL_API_TOKEN para leer trazas. Escribilo arriba y volvé a cargar.", "warn");
    return;
  }

  setStatus("Consola lista para cargar clientes y sesiones.", "ok");
}

async function loadClients() {
  if (!state.traceEnabled) {
    return;
  }
  if (state.tokenRequired && !els.internalToken.value.trim()) {
    state.clients = [];
    renderClients();
    setStatus("Falta INTERNAL_API_TOKEN. Sin eso la consola no puede listar sesiones.", "warn");
    return;
  }
  try {
    const payload = await fetchJson(`${API_PREFIX}/debug/turn-traces/clients`, { requireAuth: true });
    state.clients = payload.clients || [];
    renderClients();
    if (!state.clientId && state.clients.length) {
      state.clientId = state.clients[0].client_id;
      els.clientId.value = state.clientId;
      persistFormState();
    }
    if (state.clientId && !state.clients.some((client) => client.client_id === state.clientId) && state.clients.length) {
      state.clientId = state.clients[0].client_id;
      els.clientId.value = state.clientId;
      persistFormState();
    }
    if (state.clientId) {
      await loadSessions();
    }
  } catch (error) {
    state.clients = [];
    renderClients();
    setStatus(error.message, "error");
  }
}

async function loadSessions() {
  state.clientId = els.clientId.value.trim();
  persistFormState();
  state.sessionId = "";
  state.turn = null;
  state.sessions = [];
  state.turns = [];
  state.trace = null;
  renderSessions();
  renderTurns();
  renderTrace();

  if (!state.clientId) {
    els.sessionsList.innerHTML = `<div class="empty">Selecciona o escribe un client_id.</div>`;
    setStatus("Elegí un client_id para listar sus sesiones.", "info");
    return;
  }

  try {
    const payload = await fetchJson(
      `${API_PREFIX}/debug/turn-traces/clients/${encodeURIComponent(state.clientId)}/sessions`,
      { requireAuth: true }
    );
    state.sessions = payload.sessions || [];
    renderClients();
    renderSessions();
    if (state.sessions.length) {
      setStatus(`Se cargaron ${state.sessions.length} sesiones para ${state.clientId}.`, "ok");
    } else {
      setStatus(`No encontré sesiones para ${state.clientId}.`, "warn");
    }
  } catch (error) {
    els.sessionsList.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    setStatus(error.message, "error");
  }
}

async function loadTurns() {
  state.turns = [];
  state.trace = null;
  renderTurns();
  renderTrace();
  if (!state.clientId || !state.sessionId) {
    return;
  }
  try {
    const payload = await fetchJson(
      `${API_PREFIX}/debug/turn-traces/clients/${encodeURIComponent(state.clientId)}/sessions/${encodeURIComponent(state.sessionId)}/turns`,
      { requireAuth: true }
    );
    state.turns = payload.turns || [];
    renderTurns();
  } catch (error) {
    els.turnsList.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    setStatus(error.message, "error");
  }
}

async function loadTurnDetail() {
  state.trace = null;
  renderTrace();
  if (!state.clientId || !state.sessionId || state.turn == null) {
    return;
  }
  try {
    state.trace = await fetchJson(
      `${API_PREFIX}/debug/turn-traces/clients/${encodeURIComponent(state.clientId)}/sessions/${encodeURIComponent(state.sessionId)}/turns/${encodeURIComponent(state.turn)}`,
      { requireAuth: true }
    );
    renderTrace();
  } catch (error) {
    els.turnSummary.className = "summary-card error";
    els.turnSummary.textContent = error.message;
    setStatus(error.message, "error");
  }
}

async function deleteCurrentSession() {
  if (!state.clientId || !state.sessionId) {
    setStatus("Selecciona una sesion antes de borrarla.", "warn");
    return;
  }

  const confirmed = window.confirm(
    `Se va a borrar la traza completa de la sesion ${state.sessionId}. Esta accion no se puede deshacer.`
  );
  if (!confirmed) {
    return;
  }

  const sessionId = state.sessionId;
  try {
    const payload = await fetchJson(
      `${API_PREFIX}/debug/turn-traces/clients/${encodeURIComponent(state.clientId)}/sessions/${encodeURIComponent(sessionId)}`,
      { method: "DELETE", requireAuth: true }
    );
    state.sessionId = "";
    state.turn = null;
    state.turns = [];
    state.trace = null;
    renderTurns();
    renderTrace();
    await loadClients();
    if (payload.deleted) {
      setStatus(`Se borro la sesion ${sessionId}. Turnos eliminados: ${payload.deleted_turns}.`, "ok");
    } else {
      setStatus(`La sesion ${sessionId} ya no existia.`, "warn");
    }
  } catch (error) {
    setStatus(error.message, "error");
  }
}

els.loadSessions.addEventListener("click", async () => {
  persistFormState();
  await loadSessions();
});

els.deleteSession.addEventListener("click", async () => {
  await deleteCurrentSession();
});

els.expandDetail.addEventListener("click", () => {
  openDetailModal();
});

els.closeDetailModal.addEventListener("click", () => {
  closeDetailModal();
});

els.detailModal.addEventListener("click", (event) => {
  if (event.target instanceof HTMLElement && event.target.dataset.closeModal === "true") {
    closeDetailModal();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && isDetailModalOpen()) {
    closeDetailModal();
  }
});

els.internalToken.addEventListener("change", async () => {
  persistFormState();
  await loadConfig();
  await loadClients();
});

els.clientId.addEventListener("change", () => {
  state.clientId = els.clientId.value.trim();
  persistFormState();
  renderClients();
});

async function bootstrap() {
  restoreFormState();
  renderClients();
  renderSessions();
  renderTurns();
  renderTrace();
  updateSessionActions();
  updateDetailActions();
  try {
    await loadConfig();
    await loadClients();
  } catch (error) {
    setStatus(error.message, "error");
  }
}

bootstrap();
