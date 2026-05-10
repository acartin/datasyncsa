const PAGE_SIZE = 100;
const dataApi = window.PriceScrapperData;

const state = {
  chains: [],
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

function getSelectedChain() {
  return state.chains.find((chain) => chain.chain_id === state.catalogFilter) || null;
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

function createEmptyState(message) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  return empty;
}

function countProductsForChain(chainId) {
  return state.allProducts.filter((product) => product.available_chains.includes(chainId)).length;
}

function populateCatalogSelect() {
  elements.catalogSelect.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = `Todos los productos (${state.allProducts.length.toLocaleString("es-CR")})`;
  elements.catalogSelect.appendChild(allOption);

  state.chains.forEach((chain) => {
    const option = document.createElement("option");
    option.value = chain.chain_id;
    option.textContent = `${chain.label} (${countProductsForChain(chain.chain_id).toLocaleString(
      "es-CR"
    )})`;
    elements.catalogSelect.appendChild(option);
  });

  elements.catalogSelect.value = state.catalogFilter;
}

function applyFilters() {
  const query = dataApi.normalizeText(state.searchTerm);
  const baseProducts =
    state.catalogFilter === "all"
      ? state.allProducts
      : state.allProducts.filter((product) => product.available_chains.includes(state.catalogFilter));

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
  const selectedChain = getSelectedChain();
  const scopeLabel = selectedChain ? selectedChain.label : "todas las cadenas";

  elements.totalProducts.textContent = state.allProducts.length.toLocaleString("es-CR");
  elements.visibleProducts.textContent = state.filtered.length.toLocaleString("es-CR");
  elements.loadedCatalogs.textContent = state.chains.length.toLocaleString("es-CR");
  elements.pageIndicator.textContent = totalPages
    ? `${state.currentPage} / ${totalPages}`
    : "0 / 0";

  elements.resultsCopy.textContent = pageItems.length
    ? `Mostrando ${firstVisible}-${lastVisible} de ${state.filtered.length.toLocaleString(
        "es-CR"
      )} productos en ${scopeLabel}.`
    : `No hay coincidencias en ${scopeLabel} para la búsqueda actual.`;
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
  const loadedNames = state.chains.map((chain) => chain.shortLabel).join(", ");
  const parts = [`${state.chains.length} cadenas cargadas`];

  if (loadedNames) {
    parts.push(`(${loadedNames})`);
  }

  return parts.join(" ");
}

async function init() {
  bindEvents();
  setStatus("Cargando catálogo único desde BD...", "info");

  try {
    const { products, chains } = await dataApi.loadProductCatalog();
    if (!products.length) {
      throw new Error(
        "No se pudo cargar ningún producto desde BD. Levanta `python3 commands/serve_web.py` en services/price-scrapper y abre /web/."
      );
    }

    state.chains = chains;
    state.allProducts = dataApi.prepareCatalogProducts(products);
    state.currentPage = state.allProducts.length ? 1 : 0;

    populateCatalogSelect();
    applyFilters();
    setStatus(buildLoadedMessage(), "info");
  } catch (error) {
    elements.productGrid.innerHTML = "";
    elements.productGrid.appendChild(
      createEmptyState("No se pudieron cargar los productos desde BD.")
    );
    setStatus(error.message, "error");
    renderSummary();
    renderPagination();
  }
}

init();
