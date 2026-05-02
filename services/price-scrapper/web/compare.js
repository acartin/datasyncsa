const dataApi = window.PriceScrapperData;

const state = {
  bundles: [],
  failures: [],
  allProducts: [],
  matches: [],
  targetEan: "",
  originSource: "",
  originSku: "",
};

const elements = {
  compareForm: document.getElementById("compare-form"),
  eanInput: document.getElementById("ean-input"),
  matchCount: document.getElementById("match-count"),
  storeCount: document.getElementById("store-count"),
  loadedCatalogs: document.getElementById("loaded-catalogs"),
  resultsCopy: document.getElementById("results-copy"),
  statusBanner: document.getElementById("status-banner"),
  originPanel: document.getElementById("origin-panel"),
  productGrid: document.getElementById("product-grid"),
  template: document.getElementById("compare-card-template"),
};

function readQuery() {
  const params = new URLSearchParams(window.location.search);
  return {
    ean: String(params.get("ean") || "").trim(),
    source: String(params.get("source") || "").trim(),
    sku: String(params.get("sku") || "").trim(),
  };
}

function setStatus(message, type = "info") {
  elements.statusBanner.textContent = message;
  elements.statusBanner.classList.add("is-visible");
  elements.statusBanner.classList.toggle("is-error", type === "error");
}

function createEmptyState(message) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  return empty;
}

function findOriginProduct() {
  if (!state.targetEan) {
    return null;
  }

  return (
    state.allProducts.find(
      (product) =>
        product.ean === state.targetEan &&
        product._catalogId === state.originSource &&
        String(product.sku || "") === String(state.originSku || "")
    ) || null
  );
}

function isOriginProduct(product) {
  return (
    Boolean(state.targetEan) &&
    product.ean === state.targetEan &&
    product._catalogId === state.originSource &&
    String(product.sku || "") === String(state.originSku || "")
  );
}

function renderOrigin() {
  const origin = findOriginProduct();
  elements.originPanel.innerHTML = "";

  if (!origin) {
    elements.originPanel.classList.remove("is-visible");
    return;
  }

  const card = document.createElement("article");
  card.className = "origin-card";

  const title = document.createElement("h2");
  title.className = "origin-title";
  title.textContent = "Producto origen";

  const name = document.createElement("p");
  name.className = "origin-name";
  name.textContent = origin.name || "Sin nombre";

  const meta = document.createElement("div");
  meta.className = "origin-meta";
  meta.innerHTML = `
    <span class="origin-chip">${origin._catalogLabel}</span>
    <span class="origin-chip">SKU ${origin.sku || "-"}</span>
    <span class="origin-chip">EAN ${origin.ean || "-"}</span>
    <span class="origin-chip">${dataApi.formatCurrency(origin.price)}</span>
  `;

  const link = document.createElement("a");
  link.className = "product-link";
  link.href = origin.link || "#";
  link.target = "_blank";
  link.rel = "noreferrer noopener";
  link.textContent = "Ver producto origen";

  card.appendChild(title);
  card.appendChild(name);
  card.appendChild(meta);
  card.appendChild(link);

  elements.originPanel.appendChild(card);
  elements.originPanel.classList.add("is-visible");
}

function renderMatches() {
  elements.productGrid.innerHTML = "";

  if (!state.targetEan) {
    elements.productGrid.appendChild(
      createEmptyState("Escribe un EAN o entra desde un producto del catalogo principal.")
    );
    return;
  }

  if (!state.matches.length) {
    elements.productGrid.appendChild(
      createEmptyState("No encontramos coincidencias para ese EAN en las salidas cargadas.")
    );
    return;
  }

  const fragment = document.createDocumentFragment();
  state.matches.forEach((product) => {
    const card = elements.template.content.firstElementChild.cloneNode(true);
    dataApi.fillProductCard(card, product, {
      showCompare: false,
      highlightOrigin: isOriginProduct(product),
    });
    fragment.appendChild(card);
  });

  elements.productGrid.appendChild(fragment);
}

function renderSummary() {
  const uniqueStores = new Set(state.matches.map((product) => product._catalogId));

  elements.matchCount.textContent = state.matches.length.toLocaleString("es-CR");
  elements.storeCount.textContent = uniqueStores.size.toLocaleString("es-CR");
  elements.loadedCatalogs.textContent = state.bundles.length.toLocaleString("es-CR");

  if (!state.targetEan) {
    elements.resultsCopy.textContent = "Esperando un EAN para comparar.";
    return;
  }

  if (!state.matches.length) {
    elements.resultsCopy.textContent = `No hay coincidencias cargadas para el EAN ${state.targetEan}.`;
    return;
  }

  elements.resultsCopy.textContent = `Se encontraron ${state.matches.length.toLocaleString(
    "es-CR"
  )} coincidencias para el EAN ${state.targetEan} en ${uniqueStores.size.toLocaleString(
    "es-CR"
  )} tiendas.`;
}

function sortMatches(products) {
  return [...products].sort((left, right) => {
    const leftOrigin = isOriginProduct(left) ? 1 : 0;
    const rightOrigin = isOriginProduct(right) ? 1 : 0;

    if (leftOrigin !== rightOrigin) {
      return rightOrigin - leftOrigin;
    }

    return (
      left._catalogLabel.localeCompare(right._catalogLabel, "es") ||
      left.name.localeCompare(right.name, "es") ||
      Number(left.price || 0) - Number(right.price || 0)
    );
  });
}

function updateComparison() {
  if (!state.targetEan) {
    state.matches = [];
    renderOrigin();
    renderSummary();
    renderMatches();
    return;
  }

  state.matches = sortMatches(
    state.allProducts.filter((product) => String(product.ean || "").trim() === state.targetEan)
  );

  renderOrigin();
  renderSummary();
  renderMatches();
}

function bindEvents() {
  elements.compareForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const nextEan = String(elements.eanInput.value || "").trim();
    window.location.href = dataApi.buildCompareUrl({ ean: nextEan });
  });
}

function buildLoadedMessage() {
  const loadedNames = state.bundles.map((bundle) => bundle.shortLabel).join(", ");
  const parts = [`${state.bundles.length} salidas cargadas`];

  if (loadedNames) {
    parts.push(`(${loadedNames})`);
  }

  if (state.failures.length) {
    parts.push(`| ${state.failures.length} salidas omitidas`);
  }

  return parts.join(" ");
}

async function init() {
  const query = readQuery();
  state.targetEan = query.ean;
  state.originSource = query.source;
  state.originSku = query.sku;
  elements.eanInput.value = state.targetEan;

  bindEvents();
  setStatus("Cargando salidas locales para comparar...", "info");

  try {
    const { bundles, failures } = await dataApi.loadCatalogBundles();
    if (!bundles.length) {
      throw new Error(
        "No se pudo cargar ningun catalogo para comparar. Levanta un servidor desde services/price-scrapper y abre /web/."
      );
    }

    state.bundles = bundles;
    state.failures = failures;
    state.allProducts = bundles.flatMap((bundle) => dataApi.prepareProductsFromBundle(bundle));

    updateComparison();
    setStatus(buildLoadedMessage(), "info");
  } catch (error) {
    elements.productGrid.innerHTML = "";
    elements.productGrid.appendChild(
      createEmptyState("No se pudieron cargar las salidas para comparar.")
    );
    elements.originPanel.innerHTML = "";
    renderSummary();
    setStatus(error.message, "error");
  }
}

init();
