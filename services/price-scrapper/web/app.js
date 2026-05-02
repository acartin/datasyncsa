const PAGE_SIZE = 100;
const dataApi = window.PriceScrapperData;

const state = {
  bundles: [],
  failures: [],
  allProducts: [],
  filtered: [],
  currentPage: 1,
  searchTerm: "",
  catalogFilter: "all",
};

const elements = {
  searchInput: document.getElementById("search-input"),
  catalogSelect: document.getElementById("catalog-select"),
  totalProducts: document.getElementById("total-products"),
  visibleProducts: document.getElementById("visible-products"),
  pageIndicator: document.getElementById("page-indicator"),
  loadedCatalogs: document.getElementById("loaded-catalogs"),
  resultsCopy: document.getElementById("results-copy"),
  statusBanner: document.getElementById("status-banner"),
  productGrid: document.getElementById("product-grid"),
  prevButton: document.getElementById("prev-button"),
  nextButton: document.getElementById("next-button"),
  pageButtons: document.getElementById("page-buttons"),
  template: document.getElementById("product-card-template"),
};

function getSelectedBundle() {
  return state.bundles.find((bundle) => bundle.id === state.catalogFilter) || null;
}

function getTotalPages() {
  return state.filtered.length ? Math.ceil(state.filtered.length / PAGE_SIZE) : 0;
}

function getPageItems() {
  if (!state.filtered.length) {
    return [];
  }

  const start = (state.currentPage - 1) * PAGE_SIZE;
  return state.filtered.slice(start, start + PAGE_SIZE);
}

function setStatus(message, type = "info") {
  elements.statusBanner.textContent = message;
  elements.statusBanner.classList.add("is-visible");
  elements.statusBanner.classList.toggle("is-error", type === "error");
}

function clearStatus() {
  elements.statusBanner.textContent = "";
  elements.statusBanner.classList.remove("is-visible", "is-error");
}

function createEmptyState(message) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  return empty;
}

function populateCatalogSelect() {
  elements.catalogSelect.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = `Todas las salidas (${state.allProducts.length.toLocaleString("es-CR")})`;
  elements.catalogSelect.appendChild(allOption);

  state.bundles.forEach((bundle) => {
    const option = document.createElement("option");
    option.value = bundle.id;
    option.textContent = `${bundle.label} (${bundle.products.length.toLocaleString("es-CR")})`;
    elements.catalogSelect.appendChild(option);
  });

  elements.catalogSelect.value = state.catalogFilter;
}

function applyFilters() {
  const query = dataApi.normalizeText(state.searchTerm);
  const baseProducts =
    state.catalogFilter === "all"
      ? state.allProducts
      : state.allProducts.filter((product) => product._catalogId === state.catalogFilter);

  state.filtered = !query
    ? [...baseProducts]
    : baseProducts.filter((product) => product._searchIndex.includes(query));

  state.currentPage = state.filtered.length ? 1 : 0;
  render();
}

function renderPagination() {
  const totalPages = getTotalPages();
  const current = state.currentPage || 0;
  elements.pageButtons.innerHTML = "";

  if (!totalPages) {
    elements.prevButton.disabled = true;
    elements.nextButton.disabled = true;
    return;
  }

  const buttons = [];
  const start = Math.max(1, current - 2);
  const end = Math.min(totalPages, current + 2);

  buttons.push(1);
  for (let page = start; page <= end; page += 1) {
    buttons.push(page);
  }
  buttons.push(totalPages);

  const uniquePages = [...new Set(buttons)].sort((a, b) => a - b);
  let previousPage = 0;

  uniquePages.forEach((page) => {
    if (previousPage && page - previousPage > 1) {
      const separator = document.createElement("span");
      separator.className = "page-number";
      separator.textContent = "...";
      separator.setAttribute("aria-hidden", "true");
      elements.pageButtons.appendChild(separator);
    }

    const button = document.createElement("button");
    button.className = `page-number${page === current ? " is-active" : ""}`;
    button.type = "button";
    button.textContent = String(page);
    button.disabled = page === current;
    button.addEventListener("click", () => {
      state.currentPage = page;
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    elements.pageButtons.appendChild(button);
    previousPage = page;
  });

  elements.prevButton.disabled = current <= 1;
  elements.nextButton.disabled = current >= totalPages;
}

function renderGrid() {
  const products = getPageItems();
  elements.productGrid.innerHTML = "";

  if (!products.length) {
    elements.productGrid.appendChild(
      createEmptyState("No hay productos para mostrar con el filtro actual.")
    );
    return;
  }

  const fragment = document.createDocumentFragment();
  products.forEach((product) => {
    const card = elements.template.content.firstElementChild.cloneNode(true);
    dataApi.fillProductCard(card, product);
    fragment.appendChild(card);
  });

  elements.productGrid.appendChild(fragment);
}

function renderSummary() {
  const totalPages = getTotalPages();
  const pageItems = getPageItems();
  const firstVisible =
    pageItems.length && state.currentPage ? (state.currentPage - 1) * PAGE_SIZE + 1 : 0;
  const lastVisible = pageItems.length ? firstVisible + pageItems.length - 1 : 0;
  const selectedBundle = getSelectedBundle();
  const scopeLabel = selectedBundle ? selectedBundle.label : "todas las salidas";

  elements.totalProducts.textContent = state.allProducts.length.toLocaleString("es-CR");
  elements.visibleProducts.textContent = state.filtered.length.toLocaleString("es-CR");
  elements.loadedCatalogs.textContent = state.bundles.length.toLocaleString("es-CR");
  elements.pageIndicator.textContent = totalPages
    ? `${state.currentPage} / ${totalPages}`
    : "0 / 0";

  elements.resultsCopy.textContent = pageItems.length
    ? `Mostrando ${firstVisible}-${lastVisible} de ${state.filtered.length.toLocaleString(
        "es-CR"
      )} productos en ${scopeLabel}.`
    : `No hay coincidencias en ${scopeLabel} para la busqueda actual.`;
}

function render() {
  renderSummary();
  renderGrid();
  renderPagination();
}

function bindEvents() {
  elements.searchInput.addEventListener("input", (event) => {
    state.searchTerm = event.target.value;
    applyFilters();
  });

  elements.catalogSelect.addEventListener("change", (event) => {
    state.catalogFilter = event.target.value;
    applyFilters();
  });

  elements.prevButton.addEventListener("click", () => {
    if (state.currentPage > 1) {
      state.currentPage -= 1;
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

  elements.nextButton.addEventListener("click", () => {
    if (state.currentPage < getTotalPages()) {
      state.currentPage += 1;
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
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
  bindEvents();
  setStatus("Cargando salidas locales...", "info");

  try {
    const { bundles, failures } = await dataApi.loadCatalogBundles();
    if (!bundles.length) {
      throw new Error(
        "No se pudo cargar ningun catalogo. Levanta un servidor desde services/price-scrapper y abre /web/."
      );
    }

    state.bundles = bundles;
    state.failures = failures;
    state.allProducts = bundles.flatMap((bundle) => dataApi.prepareProductsFromBundle(bundle));
    state.currentPage = state.allProducts.length ? 1 : 0;

    populateCatalogSelect();
    applyFilters();
    setStatus(buildLoadedMessage(), "info");
  } catch (error) {
    elements.productGrid.innerHTML = "";
    elements.productGrid.appendChild(
      createEmptyState("No se pudieron cargar las salidas locales.")
    );
    setStatus(error.message, "error");
    renderSummary();
    renderPagination();
  }
}

init();
