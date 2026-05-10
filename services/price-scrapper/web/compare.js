const dataApi = window.PriceScrapperData;

const state = {
  chains: [],
  catalogProducts: [],
  matches: [],
  selectedProduct: null,
  targetProductKey: null,
  targetEan: "",
  searchQuery: "",
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
  const productKeyText = String(params.get("product_key") || "").trim();
  const parsedProductKey = Number.parseInt(productKeyText, 10);

  return {
    productKey: Number.isFinite(parsedProductKey) ? parsedProductKey : null,
    ean: String(params.get("ean") || "").trim(),
    q: String(params.get("q") || "").trim(),
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

function isExactComparisonMode() {
  return Boolean(state.selectedProduct && state.targetProductKey);
}

function renderOrigin() {
  elements.originPanel.innerHTML = "";

  if (!state.selectedProduct) {
    elements.originPanel.classList.remove("is-visible");
    return;
  }

  const product = state.selectedProduct;
  const card = document.createElement("article");
  card.className = "origin-card";

  const title = document.createElement("h2");
  title.className = "origin-title";
  title.textContent = "Producto canónico";

  const name = document.createElement("p");
  name.className = "origin-name";
  name.textContent = product.name || "Sin nombre";

  const meta = document.createElement("div");
  meta.className = "origin-meta";
  meta.innerHTML = `
    <span class="origin-chip">${product.brand || "Marca no disponible"}</span>
    <span class="origin-chip">EAN ${product.ean || "-"}</span>
    <span class="origin-chip">${product.available_chain_count || 0} cadenas</span>
    <span class="origin-chip">${product.quantity && product.unit ? `${product.quantity} ${product.unit}` : "Medida no disponible"}</span>
  `;

  const link = document.createElement("a");
  link.className = "product-link";
  link.href = product.link || "#";
  link.target = "_blank";
  link.rel = "noreferrer noopener";
  link.textContent = "Ver producto de referencia";
  if (!product.link) {
    link.setAttribute("aria-disabled", "true");
    link.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
      },
      { once: true }
    );
  }

  card.appendChild(title);
  card.appendChild(name);
  card.appendChild(meta);
  card.appendChild(link);

  elements.originPanel.appendChild(card);
  elements.originPanel.classList.add("is-visible");
}

function renderMatches() {
  elements.productGrid.innerHTML = "";

  if (!state.targetProductKey && !state.searchQuery) {
    elements.productGrid.appendChild(
      createEmptyState("Escribe un nombre, marca, SKU o EAN para buscar y comparar.")
    );
    return;
  }

  if (!state.matches.length) {
    elements.productGrid.appendChild(
      createEmptyState(
        isExactComparisonMode()
          ? "No encontramos snapshots comparativos vigentes para ese producto."
          : "No encontramos coincidencias para esa búsqueda en el catálogo único."
      )
    );
    return;
  }

  const fragment = document.createDocumentFragment();
  state.matches.forEach((product) => {
    const card = elements.template.content.firstElementChild.cloneNode(true);
    dataApi.fillProductCard(card, product, {
      showCompare: !isExactComparisonMode(),
      compareText: "Comparar",
      highlightOrigin: false,
    });
    fragment.appendChild(card);
  });

  elements.productGrid.appendChild(fragment);
}

function renderSummary() {
  const uniqueStores = new Set(
    state.matches.map((product) => product.chain || product._catalogId).filter(Boolean)
  );

  elements.matchCount.textContent = state.matches.length.toLocaleString("es-CR");
  elements.storeCount.textContent = uniqueStores.size.toLocaleString("es-CR");
  elements.loadedCatalogs.textContent = state.chains.length.toLocaleString("es-CR");

  if (!state.targetProductKey && !state.searchQuery) {
    elements.resultsCopy.textContent = "Esperando un criterio de búsqueda para comparar.";
    return;
  }

  if (!state.matches.length) {
    elements.resultsCopy.textContent = isExactComparisonMode()
      ? `No hay snapshots comparativos cargados para ${state.selectedProduct?.name || "este producto"}.`
      : `No hay coincidencias cargadas para la búsqueda "${state.searchQuery}".`;
    return;
  }

  if (isExactComparisonMode()) {
    elements.resultsCopy.textContent = `Se encontraron ${state.matches.length.toLocaleString(
      "es-CR"
    )} snapshots actuales para ${state.selectedProduct?.name || "el producto"} en ${uniqueStores.size.toLocaleString(
      "es-CR"
    )} cadenas.`;
    return;
  }

  elements.resultsCopy.textContent = `Se encontraron ${state.matches.length.toLocaleString(
    "es-CR"
  )} productos para "${state.searchQuery}" en el catálogo único.`;
}

function sortSearchMatches(products) {
  return [...products].sort((left, right) => {
    return (
      Number(right.available_chain_count || 0) - Number(left.available_chain_count || 0) ||
      left.name.localeCompare(right.name, "es") ||
      left.brand.localeCompare(right.brand, "es")
    );
  });
}

function sortComparisonMatches(products) {
  return [...products].sort((left, right) => {
    return (
      Number(left.price ?? Number.MAX_SAFE_INTEGER) - Number(right.price ?? Number.MAX_SAFE_INTEGER) ||
      String(left._catalogLabel || "").localeCompare(String(right._catalogLabel || ""), "es")
    );
  });
}

async function updateComparison() {
  renderOrigin();

  if (isExactComparisonMode()) {
    const payload = await dataApi.loadProductComparison({
      productKey: state.targetProductKey,
      ean: state.targetEan,
    });
    state.matches = sortComparisonMatches(
      dataApi.prepareCatalogProducts(payload.matches).map((product) => ({
        ...product,
        _catalogSource: "/api/product-comparison",
      }))
    );
    renderSummary();
    renderMatches();
    return;
  }

  if (!state.searchQuery) {
    state.matches = [];
    renderSummary();
    renderMatches();
    return;
  }

  const query = dataApi.normalizeText(state.searchQuery);
  state.matches = sortSearchMatches(
    state.catalogProducts.filter((product) => product._searchIndex.includes(query))
  );
  renderSummary();
  renderMatches();
}

function bindEvents() {
  elements.compareForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const nextQuery = String(elements.eanInput.value || "").trim();
    if (!nextQuery) {
      window.location.href = dataApi.buildCompareUrl({});
      return;
    }

    const exactProductMatch = state.catalogProducts.find(
      (product) =>
        String(product.ean || "").trim() === nextQuery ||
        String(product.product_key || "").trim() === nextQuery
    );

    window.location.href = exactProductMatch
      ? dataApi.buildCompareUrl({
          productKey: exactProductMatch.product_key,
          ean: exactProductMatch.ean,
        })
      : dataApi.buildCompareUrl({ q: nextQuery });
  });
}

function buildLoadedMessage() {
  const loadedNames = state.chains.map((chain) => chain.shortLabel).join(", ");
  const parts = [`${state.chains.length} cadenas cargadas`];

  if (loadedNames) {
    parts.push(`(${loadedNames})`);
  }

  return parts.join(" ");
}

async function init() {
  const query = readQuery();
  state.targetProductKey = query.productKey;
  state.targetEan = query.ean;
  state.searchQuery = query.q || query.ean;
  elements.eanInput.value = query.q || query.ean || (query.productKey ? String(query.productKey) : "");

  bindEvents();
  setStatus("Cargando catálogo único desde BD para comparar...", "info");

  try {
    const { products, chains } = await dataApi.loadProductCatalog();
    if (!products.length) {
      throw new Error(
        "No se pudo cargar ningún producto para comparar desde BD. Levanta `python3 commands/serve_web.py` en services/price-scrapper y abre /web/."
      );
    }

    state.chains = chains;
    state.catalogProducts = dataApi.prepareCatalogProducts(products);

    if (state.targetProductKey) {
      state.selectedProduct =
        state.catalogProducts.find((product) => product.product_key === state.targetProductKey) ||
        null;
    } else if (state.targetEan && !query.q) {
      state.selectedProduct =
        state.catalogProducts.find((product) => String(product.ean || "").trim() === state.targetEan) ||
        null;
      if (state.selectedProduct) {
        state.targetProductKey = state.selectedProduct.product_key;
      }
    }

    await updateComparison();
    setStatus(buildLoadedMessage(), "info");
  } catch (error) {
    elements.productGrid.innerHTML = "";
    elements.productGrid.appendChild(
      createEmptyState("No se pudieron cargar los datos para comparar desde BD.")
    );
    elements.originPanel.innerHTML = "";
    renderSummary();
    setStatus(error.message, "error");
  }
}

init();
