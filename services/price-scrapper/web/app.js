const PAGE_SIZE = 100;
const CART_COOKIE_NAME = "mw_compare_cart";
const CART_MAX_ITEMS = 80;
const dataApi = window.PriceScrapperData;

const state = {
  chains: [],
  allProducts: [],
  filtered: [],
  currentPage: 1,
  searchTerm: "",
  catalogFilter: "all",
  cartProductKeys: [],
  cartPlan: null,
  cartLoading: false,
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
  cartCopy: document.getElementById("cart-copy"),
  cartCount: document.getElementById("cart-count"),
  cartPlanButton: document.getElementById("cart-plan-button"),
  cartClearButton: document.getElementById("cart-clear-button"),
  cartStatus: document.getElementById("cart-status"),
  cartEmpty: document.getElementById("cart-empty"),
  cartItems: document.getElementById("cart-items"),
  cartPlan: document.getElementById("cart-plan"),
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

function readCookie(name) {
  const prefix = `${name}=`;
  const cookie = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix));

  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : "";
}

function writeCookie(name, value, maxAgeDays = 45) {
  const maxAge = Math.max(1, maxAgeDays) * 24 * 60 * 60;
  document.cookie = `${name}=${encodeURIComponent(value)}; max-age=${maxAge}; path=/; SameSite=Lax`;
}

function normalizeCartKeys(keys) {
  return [
    ...new Set(
      (keys || []).map((key) => Number(key)).filter((key) => Number.isInteger(key) && key > 0)
    ),
  ].slice(0, CART_MAX_ITEMS);
}

function loadCartCookie() {
  try {
    const raw = readCookie(CART_COOKIE_NAME);
    return raw ? normalizeCartKeys(JSON.parse(raw)) : [];
  } catch (_error) {
    return [];
  }
}

function saveCartCookie() {
  writeCookie(CART_COOKIE_NAME, JSON.stringify(state.cartProductKeys));
}

function findProductByKey(productKey) {
  const key = Number(productKey);
  return state.allProducts.find((product) => Number(product.product_key) === key) || null;
}

function getCartProducts() {
  return state.cartProductKeys.map((key) => findProductByKey(key)).filter(Boolean);
}

function syncCartWithCatalog() {
  state.cartProductKeys = normalizeCartKeys(state.cartProductKeys).filter((key) =>
    findProductByKey(key)
  );
  saveCartCookie();
}

function setCartStatus(message, type = "info") {
  elements.cartStatus.textContent = message || "";
  elements.cartStatus.classList.toggle("is-visible", Boolean(message));
  elements.cartStatus.classList.toggle("is-error", type === "error");
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
    const cartButton = card.querySelector(".cart-link");
    const productKey = Number(product.product_key);
    const isInCart = state.cartProductKeys.includes(productKey);

    if (cartButton) {
      cartButton.textContent = isInCart ? "En carrito" : "Agregar al carrito";
      cartButton.disabled = isInCart || !productKey;
      cartButton.addEventListener("click", () => addToCart(productKey));
    }

    fragment.appendChild(card);
  });

  elements.productGrid.appendChild(fragment);
}

function createCartItem(product) {
  const item = document.createElement("article");
  item.className = "cart-item";

  const body = document.createElement("div");
  body.className = "cart-item-body";

  const name = document.createElement("h3");
  name.textContent = product.name || "Producto sin nombre";

  const meta = document.createElement("p");
  meta.textContent = [
    product.brand || "Marca no disponible",
    product.ean ? `EAN ${product.ean}` : null,
    `${product.available_chain_count || product.available_chains.length || 0} cadenas`,
  ]
    .filter(Boolean)
    .join(" · ");

  body.append(name, meta);

  const actions = document.createElement("div");
  actions.className = "cart-item-actions";

  const compare = document.createElement("a");
  compare.className = "compare-link";
  compare.href = dataApi.buildCompareHref(product);
  compare.textContent = "Comparar";

  const remove = document.createElement("button");
  remove.className = "cart-remove";
  remove.type = "button";
  remove.textContent = "Quitar";
  remove.addEventListener("click", () => removeFromCart(product.product_key));

  actions.append(compare, remove);
  item.append(body, actions);
  return item;
}

function renderPlanGroup(group) {
  const card = document.createElement("div");
  card.className = "cart-plan-card";

  const title = document.createElement("h3");
  title.textContent = group.chainLabel;

  const total = document.createElement("strong");
  total.className = "cart-total";
  total.textContent = dataApi.formatCurrency(group.total);

  const list = document.createElement("ul");
  group.items.forEach((item) => {
    const entry = document.createElement("li");
    entry.textContent = `${item.product.name} · ${dataApi.formatCurrency(
      item.bestMatch.price
    )} · ${dataApi.formatUnitPrice(item.bestMatch)}`;
    list.appendChild(entry);
  });

  card.append(title, total, list);
  return card;
}

function renderSingleChainOption(option, totalItems) {
  const card = document.createElement("div");
  card.className = `cart-plan-card${option.missingCount ? " is-partial" : ""}`;

  const title = document.createElement("h3");
  title.textContent = option.chain.label || option.chain.shortLabel || option.chain.chain_id;

  const total = document.createElement("strong");
  total.className = "cart-total";
  total.textContent = dataApi.formatCurrency(option.total);

  const meta = document.createElement("p");
  meta.textContent = option.missingCount
    ? `${option.availableCount}/${totalItems} productos disponibles. Faltan ${option.missingCount}.`
    : "Todos los productos disponibles en esta cadena.";

  card.append(title, total, meta);
  return card;
}

function renderCartPlan() {
  elements.cartPlan.innerHTML = "";

  if (state.cartLoading) {
    const loading = document.createElement("div");
    loading.className = "cart-plan-card";
    loading.textContent = "Calculando la mejor compra por total...";
    elements.cartPlan.appendChild(loading);
    return;
  }

  if (!state.cartPlan) {
    return;
  }

  const { rows, groups, minTotal, singleChainOptions } = state.cartPlan;
  const plannedRows = rows.filter((row) => row.bestMatch);
  const missingRows = rows.filter((row) => !row.bestMatch);

  const summary = document.createElement("div");
  summary.className = "cart-plan-summary";

  const title = document.createElement("h3");
  title.textContent = "Compra por precio minimo";

  const total = document.createElement("strong");
  total.className = "cart-total is-large";
  total.textContent = dataApi.formatCurrency(minTotal);

  const meta = document.createElement("p");
  meta.textContent = `${plannedRows.length}/${rows.length} productos con precio. ${groups.length} ${
    groups.length === 1 ? "cadena sugerida" : "cadenas sugeridas"
  }.`;

  summary.append(title, total, meta);
  elements.cartPlan.appendChild(summary);

  const groupGrid = document.createElement("div");
  groupGrid.className = "cart-plan-grid";
  groups.forEach((group) => groupGrid.appendChild(renderPlanGroup(group)));
  elements.cartPlan.appendChild(groupGrid);

  const topSingleChainOptions = singleChainOptions
    .filter((option) => option.availableCount > 0)
    .slice(0, 3);

  if (topSingleChainOptions.length) {
    const singleTitle = document.createElement("h3");
    singleTitle.className = "cart-section-title";
    singleTitle.textContent = "Mejor opcion en una sola cadena";
    elements.cartPlan.appendChild(singleTitle);

    const singleGrid = document.createElement("div");
    singleGrid.className = "cart-plan-grid";
    topSingleChainOptions.forEach((option) =>
      singleGrid.appendChild(renderSingleChainOption(option, rows.length))
    );
    elements.cartPlan.appendChild(singleGrid);
  }

  if (missingRows.length) {
    const missing = document.createElement("p");
    missing.className = "cart-warning";
    missing.textContent = `Sin precio comparable para: ${missingRows
      .map((row) => row.product.name)
      .slice(0, 3)
      .join(", ")}.`;
    elements.cartPlan.appendChild(missing);
  }
}

function renderCart() {
  const products = getCartProducts();
  const count = products.length;

  elements.cartCount.textContent = `${count.toLocaleString("es-CR")} ${
    count === 1 ? "producto" : "productos"
  }`;
  elements.cartCopy.textContent = count
    ? "Calcula el total minimo y decide si conviene dividir la compra por cadena."
    : "Agrega productos para calcular el ahorro por compra total.";
  elements.cartPlanButton.disabled = !count || state.cartLoading;
  elements.cartClearButton.disabled = !count || state.cartLoading;
  elements.cartEmpty.style.display = count ? "none" : "block";
  elements.cartItems.innerHTML = "";

  products.forEach((product) => {
    elements.cartItems.appendChild(createCartItem(product));
  });

  renderCartPlan();
}

function addToCart(productKey) {
  const key = Number(productKey);
  if (!findProductByKey(key) || state.cartProductKeys.includes(key)) {
    return;
  }

  state.cartProductKeys = normalizeCartKeys([...state.cartProductKeys, key]);
  state.cartPlan = null;
  saveCartCookie();
  setCartStatus("Producto agregado al carrito.", "info");
  render();
}

function removeFromCart(productKey) {
  const key = Number(productKey);
  state.cartProductKeys = state.cartProductKeys.filter((itemKey) => itemKey !== key);
  state.cartPlan = null;
  saveCartCookie();
  setCartStatus("Producto eliminado del carrito.", "info");
  render();
}

function clearCart() {
  state.cartProductKeys = [];
  state.cartPlan = null;
  saveCartCookie();
  setCartStatus("Carrito vaciado.", "info");
  render();
}

function getBestMatch(matches) {
  return (
    matches
      .filter((match) => Number(match.price) > 0)
      .sort((left, right) => Number(left.price) - Number(right.price))[0] || null
  );
}

function buildCartPlan(rows) {
  const groupsByChain = new Map();
  let minTotal = 0;

  rows.forEach((row) => {
    if (!row.bestMatch) {
      return;
    }

    minTotal += Number(row.bestMatch.price);
    const chainId = row.bestMatch.chain || "sin_cadena";
    if (!groupsByChain.has(chainId)) {
      groupsByChain.set(chainId, {
        chainId,
        chainLabel: row.bestMatch._catalogShortLabel || row.bestMatch._catalogLabel || chainId,
        total: 0,
        items: [],
      });
    }

    const group = groupsByChain.get(chainId);
    group.total += Number(row.bestMatch.price);
    group.items.push(row);
  });

  const singleChainOptions = state.chains
    .map((chain) => {
      const matches = rows
        .map((row) =>
          row.matches.find((match) => match.chain === chain.chain_id && Number(match.price) > 0)
        )
        .filter(Boolean);
      const total = matches.reduce((sum, match) => sum + Number(match.price), 0);

      return {
        chain,
        total,
        availableCount: matches.length,
        missingCount: rows.length - matches.length,
      };
    })
    .sort((left, right) => {
      if (left.missingCount !== right.missingCount) {
        return left.missingCount - right.missingCount;
      }
      return left.total - right.total;
    });

  return {
    rows,
    minTotal,
    groups: [...groupsByChain.values()].sort((left, right) => right.total - left.total),
    singleChainOptions,
  };
}

async function planCart() {
  const products = getCartProducts();
  if (!products.length) {
    setCartStatus("Agrega productos antes de organizar la compra.", "error");
    return;
  }

  state.cartLoading = true;
  state.cartPlan = null;
  setCartStatus("", "info");
  renderCart();

  try {
    const comparisons = await Promise.all(
      products.map(async (product) => {
        const comparison = await dataApi.loadProductComparison({ productKey: product.product_key });
        const matches = comparison.matches || [];
        return {
          product,
          matches,
          bestMatch: getBestMatch(matches),
        };
      })
    );

    state.cartPlan = buildCartPlan(comparisons);
  } catch (error) {
    setCartStatus(error.message, "error");
  } finally {
    state.cartLoading = false;
    renderCart();
  }
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
  renderCart();
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

  elements.cartPlanButton.addEventListener("click", planCart);
  elements.cartClearButton.addEventListener("click", clearCart);
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
  state.cartProductKeys = loadCartCookie();
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
    syncCartWithCatalog();
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
