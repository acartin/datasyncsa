const state = {
  bundles: [],
  bundle: null,
  conversationId: null,
  suiteTypeFilter: "all",
};

const API_PREFIX = window.location.pathname.replace(/\/debug\/conversation-suites\/$/, "");

const els = {
  reloadBundles: document.getElementById("reloadBundles"),
  statusBanner: document.getElementById("statusBanner"),
  suiteTypeMeta: document.getElementById("suiteTypeMeta"),
  bundlesMeta: document.getElementById("bundlesMeta"),
  bundlesList: document.getElementById("bundlesList"),
  conversationsMeta: document.getElementById("conversationsMeta"),
  conversationsList: document.getElementById("conversationsList"),
  detailMeta: document.getElementById("detailMeta"),
  openTurnTrace: document.getElementById("openTurnTrace"),
  conversationSummary: document.getElementById("conversationSummary"),
  turnsList: document.getElementById("turnsList"),
  suiteFilters: Array.from(document.querySelectorAll("[data-suite-type]")),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function parseCompactUtcTimestamp(value) {
  const raw = String(value || "").trim();
  const match = raw.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  if (!match) {
    return null;
  }
  const [, year, month, day, hour, minute, second] = match;
  return {
    raw,
    display: `${year}-${month}-${day} ${hour}:${minute}:${second} UTC`,
  };
}

function formatBundleTimestamp(bundle) {
  const parsed =
    parseCompactUtcTimestamp(bundle?.generated_at) ||
    parseCompactUtcTimestamp(bundle?.meta?.generated_at) ||
    parseCompactUtcTimestamp(bundle?.report?.generated_at);
  if (parsed) {
    return parsed;
  }
  const fallback = String(bundle?.generated_at || bundle?.meta?.generated_at || bundle?.report?.generated_at || "").trim();
  if (!fallback) {
    return { raw: "", display: "-" };
  }
  return {
    raw: fallback,
    display: fallback,
  };
}

function setStatus(message, kind = "ok") {
  els.statusBanner.className = `status-banner status-${kind}`;
  els.statusBanner.textContent = message;
}

function inferSuiteType(bundle) {
  const explicit = String(bundle?.suite_type || bundle?.meta?.suite_type || bundle?.report?.suite_type || "").trim().toLowerCase();
  if (["generated", "regression", "manual"].includes(explicit)) {
    return explicit;
  }
  const candidates = [bundle?.bundle_id, bundle?.suite_id, bundle?.meta?.suite_id, bundle?.report?.suite_id];
  for (const candidate of candidates) {
    const normalized = String(candidate || "").trim().toLowerCase();
    if (normalized.includes("regression")) return "regression";
    if (normalized.includes("manual")) return "manual";
    if (normalized.includes("generated")) return "generated";
  }
  return "manual";
}

function getFilteredBundles() {
  if (state.suiteTypeFilter === "all") {
    return state.bundles;
  }
  return state.bundles.filter((bundle) => inferSuiteType(bundle) === state.suiteTypeFilter);
}

function updateSuiteTypeFilterUi() {
  els.suiteFilters.forEach((button) => {
    const active = button.dataset.suiteType === state.suiteTypeFilter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });

  const counts = { generated: 0, regression: 0, manual: 0 };
  state.bundles.forEach((bundle) => {
    counts[inferSuiteType(bundle)] += 1;
  });
  els.suiteTypeMeta.textContent =
    `generated: ${counts.generated} · regression: ${counts.regression} · manual: ${counts.manual}`;
}

function getBundleClientId() {
  return state.bundle?.report?.client_id || state.bundle?.meta?.client_id || null;
}

function buildTurnTraceUrl(conversation) {
  const clientId = getBundleClientId();
  const sessionId = conversation?.session_id || null;
  if (!clientId || !sessionId) {
    return null;
  }
  const params = new URLSearchParams({
    client_id: clientId,
    session_id: sessionId,
  });
  return `${API_PREFIX}/debug/turn-trace/?${params.toString()}`;
}

function renderTurnTraceLink(conversation) {
  const url = buildTurnTraceUrl(conversation);
  if (!url) {
    els.openTurnTrace.classList.add("disabled");
    els.openTurnTrace.setAttribute("aria-disabled", "true");
    els.openTurnTrace.setAttribute("href", "#");
    return;
  }
  els.openTurnTrace.classList.remove("disabled");
  els.openTurnTrace.setAttribute("aria-disabled", "false");
  els.openTurnTrace.setAttribute("href", url);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json();
}

function renderBundles() {
  const filteredBundles = getFilteredBundles();
  els.bundlesMeta.textContent = `${filteredBundles.length} bundles`;
  if (!filteredBundles.length) {
    els.bundlesList.innerHTML = `<div class="empty">No hay bundles publicados todavia.</div>`;
    return;
  }
  els.bundlesList.innerHTML = filteredBundles
    .map((bundle) => {
      const suiteType = inferSuiteType(bundle);
      const timestamp = formatBundleTimestamp(bundle);
      return `
        <button class="list-item ${state.bundle?.bundle_id === bundle.bundle_id ? "selected" : ""}" data-bundle-id="${escapeHtml(bundle.bundle_id)}">
          <div class="list-item-top">
            <strong>${escapeHtml(bundle.suite_id || bundle.bundle_id)}</strong>
            <span class="type-chip type-${escapeHtml(suiteType)}">${escapeHtml(suiteType)}</span>
          </div>
          <div class="bundle-meta-grid">
            <span>bundle: ${escapeHtml(bundle.bundle_id)}</span>
            <span>turns: ${escapeHtml(bundle.turns_total || 0)} · failed: ${escapeHtml(bundle.turns_failed || 0)}</span>
          </div>
          <div class="bundle-timestamp" title="${escapeHtml(timestamp.raw || timestamp.display)}">
            <span class="timestamp-label">timestamp</span>
            <span class="timestamp-value">${escapeHtml(timestamp.display)}</span>
          </div>
        </button>
      `;
    })
    .join("");

  els.bundlesList.querySelectorAll("[data-bundle-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await loadBundle(button.dataset.bundleId);
    });
  });
}

function renderConversations() {
  const conversations = state.bundle?.report?.conversations || [];
  els.conversationsMeta.textContent = `${conversations.length} conversaciones`;
  if (!state.bundle) {
    els.conversationsList.innerHTML = `<div class="empty">Selecciona un bundle.</div>`;
    return;
  }
  if (!conversations.length) {
    els.conversationsList.innerHTML = `<div class="empty">Este bundle no trae conversaciones en el reporte.</div>`;
    return;
  }
  els.conversationsList.innerHTML = conversations
    .map(
      (conversation) => `
        <button class="list-item ${conversation.passed ? "pass" : "fail"} ${state.conversationId === conversation.id ? "selected" : ""}" data-conversation-id="${escapeHtml(conversation.id)}">
          <strong>${escapeHtml(conversation.id)}</strong>
          <span>${escapeHtml(conversation.description || "-")}</span>
          <span>${conversation.passed ? "PASS" : "FAIL"} · turns: ${escapeHtml((conversation.turns || []).length)}</span>
        </button>
      `
    )
    .join("");

  els.conversationsList.querySelectorAll("[data-conversation-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.conversationId = button.dataset.conversationId;
      renderConversations();
      renderConversationDetail();
    });
  });
}

function renderConversationDetail() {
  if (!state.bundle || !state.conversationId) {
    els.detailMeta.textContent = "";
    renderTurnTraceLink(null);
    els.conversationSummary.className = "summary-card empty";
    els.conversationSummary.textContent = "Selecciona un bundle y una conversacion.";
    els.turnsList.innerHTML = "";
    return;
  }

  const conversation = (state.bundle.report?.conversations || []).find((item) => item.id === state.conversationId);
  if (!conversation) {
    renderTurnTraceLink(null);
    els.conversationSummary.className = "summary-card empty";
    els.conversationSummary.textContent = "No encontre esa conversacion en el reporte.";
    els.turnsList.innerHTML = "";
    return;
  }

  els.detailMeta.textContent = `${conversation.passed ? "PASS" : "FAIL"} · session_id=${conversation.session_id}`;
  renderTurnTraceLink(conversation);
  els.conversationSummary.className = `summary-card ${conversation.passed ? "pass" : "fail"}`;
  els.conversationSummary.textContent =
    `${conversation.description || "-"}\n` +
    `tags: ${(conversation.tags || []).join(", ") || "-"}\n` +
    `session_id: ${conversation.session_id}\n` +
    `conversation_id: ${conversation.conversation_id}`;

  els.turnsList.innerHTML = (conversation.turns || [])
    .map((turn) => {
      const issues = (turn.issues || [])
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join("");
      const manual = (turn.manual_review_focus || [])
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join("");
      const badges = [
        turn.dialogue_act ? `<span class="pill">dialogue_act=${escapeHtml(turn.dialogue_act)}</span>` : "",
        turn.search_match_scope ? `<span class="pill">match_scope=${escapeHtml(turn.search_match_scope)}</span>` : "",
        turn.render_mode ? `<span class="pill">render=${escapeHtml(turn.render_mode)}</span>` : "",
        turn.cards_mode ? `<span class="pill">cards=${escapeHtml(turn.cards_mode)}</span>` : "",
        `<span class="pill">components=${escapeHtml(turn.components_count || 0)}</span>`,
      ].join("");
      return `
        <article class="turn-card ${turn.passed ? "pass" : "fail"}">
          <h3>Turno ${escapeHtml(turn.turn_index)} · ${turn.passed ? "PASS" : "FAIL"}</h3>
          <p><strong>User:</strong> ${escapeHtml(turn.user_text)}</p>
          <p><strong>Answer:</strong> ${escapeHtml(turn.answer || "")}</p>
          <p>${badges}</p>
          ${issues ? `<div class="issues"><strong>Issues</strong><ul>${issues}</ul></div>` : ""}
          ${manual ? `<div class="manual"><strong>Manual Review</strong><ul>${manual}</ul></div>` : ""}
        </article>
      `;
    })
    .join("");
}

async function loadBundles() {
  setStatus("Cargando bundles...", "ok");
  try {
    const payload = await fetchJson(`${API_PREFIX}/debug/generated-conversation-suites/bundles`);
    state.bundles = payload.bundles || [];
    updateSuiteTypeFilterUi();
    renderBundles();
    renderConversations();
    renderConversationDetail();
    setStatus("Bundles cargados.", "ok");
  } catch (error) {
    setStatus(`No pude cargar los bundles: ${error.message}`, "error");
  }
}

async function loadBundle(bundleId) {
  setStatus(`Cargando bundle ${bundleId}...`, "ok");
  try {
    state.bundle = await fetchJson(`${API_PREFIX}/debug/generated-conversation-suites/bundles/${encodeURIComponent(bundleId)}`);
    const firstConversation = state.bundle?.report?.conversations?.[0]?.id || null;
    state.conversationId = firstConversation;
    updateSuiteTypeFilterUi();
    renderBundles();
    renderConversations();
    renderConversationDetail();
    setStatus(`Bundle ${bundleId} cargado.`, "ok");
  } catch (error) {
    setStatus(`No pude cargar el bundle: ${error.message}`, "error");
  }
}

els.reloadBundles.addEventListener("click", () => {
  loadBundles();
});

els.suiteFilters.forEach((button) => {
  button.addEventListener("click", () => {
    state.suiteTypeFilter = button.dataset.suiteType || "all";
    const visibleBundles = getFilteredBundles();
    if (state.bundle && !visibleBundles.some((bundle) => bundle.bundle_id === state.bundle.bundle_id)) {
      state.bundle = null;
      state.conversationId = null;
    }
    updateSuiteTypeFilterUi();
    renderBundles();
    renderConversations();
    renderConversationDetail();
  });
});

loadBundles();
