(function () {
  async function fetchJson(url, failurePrefix) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const payload = await response.json();
        if (payload?.error) {
          detail = payload.error;
        }
      } catch (_error) {
        // ignore parse errors and keep HTTP detail
      }
      throw new Error(`${failurePrefix}. Detalle: ${detail}`);
    }

    return response.json();
  }

  async function loadCatalogBundles() {
    const payload = await fetchJson(
      "/api/catalog-bundles",
      "No se pudo cargar el comparador desde BD"
    );
    if (!payload || !Array.isArray(payload.bundles)) {
      throw new Error("La API de catálogos no devolvió un payload válido.");
    }

    return {
      bundles: payload.bundles,
      failures: Array.isArray(payload.failures) ? payload.failures : [],
    };
  }

  async function loadProductCatalog() {
    const payload = await fetchJson(
      "/api/product-catalog",
      "No se pudo cargar el catálogo único desde BD"
    );
    if (!payload || !Array.isArray(payload.products)) {
      throw new Error("La API de productos no devolvió un payload válido.");
    }

    return {
      products: payload.products,
      chains: Array.isArray(payload.chains) ? payload.chains : [],
    };
  }

  async function loadProductComparison(params = {}) {
    const query = new URLSearchParams();
    if (params.productKey) {
      query.set("product_key", String(params.productKey).trim());
    }
    if (params.ean) {
      query.set("ean", String(params.ean).trim());
    }

    const suffix = query.toString();
    const payload = await fetchJson(
      `/api/product-comparison${suffix ? `?${suffix}` : ""}`,
      "No se pudo cargar la comparación desde BD"
    );
    if (!payload || !payload.product || !Array.isArray(payload.matches)) {
      throw new Error("La API de comparación no devolvió un payload válido.");
    }
    return payload;
  }

  function normalizeText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, " ")
      .trim();
  }

  function formatCurrency(value) {
    const amount = Number(value || 0);
    return new Intl.NumberFormat("es-CR", {
      style: "currency",
      currency: "CRC",
      maximumFractionDigits: 0,
    }).format(amount);
  }

  function normalizeUnit(unit) {
    return String(unit || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function getUnitPrice(product) {
    const price = Number(product?.price || 0);
    const quantity = Number(product?.quantity || 0);
    const unit = normalizeUnit(product?.unit);

    if (!price || !quantity || !unit) {
      return null;
    }

    const conversions = {
      g: { factor: 1, unit: "g" },
      gr: { factor: 1, unit: "g" },
      gramo: { factor: 1, unit: "g" },
      gramos: { factor: 1, unit: "g" },
      kg: { factor: 1000, unit: "g" },
      kilogramo: { factor: 1000, unit: "g" },
      kilogramos: { factor: 1000, unit: "g" },
      ml: { factor: 1, unit: "ml" },
      mililitro: { factor: 1, unit: "ml" },
      mililitros: { factor: 1, unit: "ml" },
      l: { factor: 1000, unit: "ml" },
      lt: { factor: 1000, unit: "ml" },
      litro: { factor: 1000, unit: "ml" },
      litros: { factor: 1000, unit: "ml" },
      un: { factor: 1, unit: "un" },
      unidad: { factor: 1, unit: "un" },
      unidades: { factor: 1, unit: "un" },
    };

    const conversion = conversions[unit];
    if (!conversion) {
      return null;
    }

    const comparableQuantity = quantity * conversion.factor;
    if (!comparableQuantity) {
      return null;
    }

    return {
      value: price / comparableQuantity,
      unit: conversion.unit,
    };
  }

  function formatUnitPrice(product) {
    const unitPrice = getUnitPrice(product);
    if (!unitPrice) {
      return "Sin precio unitario";
    }

    const value =
      unitPrice.value >= 100
        ? unitPrice.value.toLocaleString("es-CR", { maximumFractionDigits: 0 })
        : unitPrice.value.toLocaleString("es-CR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          });

    return `₡${value}/${unitPrice.unit}`;
  }

  function buildSearchIndex(product) {
    return normalizeText(
      [
        product.name,
        product.brand,
        product.category,
        product.ean,
        product.sku,
        product.product_id,
        ...(product.aliases?.listing_names || []),
        ...(product.aliases?.source_product_ids || []),
        ...(product.aliases?.source_skus || []),
        product._catalogLabel,
        product._catalogShortLabel,
      ].join(" ")
    );
  }

  function normalizeProductRecord(product) {
    return {
      ...product,
      product_key: product.product_key ? Number(product.product_key) : null,
      chain: product.chain || "",
      product_id: product.product_id || "",
      sku: product.sku || "",
      name: product.name || "",
      brand: product.brand || "",
      ean: product.ean || null,
      price: product.price ?? null,
      list_price: product.list_price ?? null,
      has_discount: Boolean(product.has_discount),
      unit: product.unit || null,
      quantity: product.quantity ?? null,
      category: product.category || "",
      link: product.link || null,
      image: product.image || null,
      pricing_scope: product.pricing_scope || null,
      available_chain_count: Number(product.available_chain_count || 0),
      available_chains: Array.isArray(product.available_chains) ? product.available_chains : [],
      aliases: {
        listing_names: Array.isArray(product.aliases?.listing_names) ? product.aliases.listing_names : [],
        source_product_ids: Array.isArray(product.aliases?.source_product_ids) ? product.aliases.source_product_ids : [],
        source_skus: Array.isArray(product.aliases?.source_skus) ? product.aliases.source_skus : [],
      },
    };
  }

  function prepareCatalogProducts(products) {
    return (products || []).map((product) => {
      const normalized = normalizeProductRecord(product);
      const prepared = {
        ...normalized,
        _catalogId: normalized._catalogId || "all",
        _catalogLabel: normalized._catalogLabel || "Catálogo único",
        _catalogShortLabel: normalized._catalogShortLabel || "Catálogo único",
        _catalogSource: normalized._catalogSource || "/api/product-catalog",
      };
      prepared._searchIndex = buildSearchIndex(prepared);
      return prepared;
    });
  }

  function prepareProductsFromBundle(bundle) {
    return (bundle.products || []).map((product) => {
      const normalized = normalizeProductRecord(product);
      const prepared = {
        ...normalized,
        _catalogId: bundle.id,
        _catalogLabel: bundle.label,
        _catalogShortLabel: bundle.shortLabel,
        _catalogSource: bundle.source || "/api/catalog-bundles",
        _generatedAt: bundle.metadata?.generated_at || bundle.metadata?.finished_at || null,
      };
      prepared._searchIndex = buildSearchIndex(prepared);
      return prepared;
    });
  }

  function buildCompareUrl(params = {}) {
    const query = new URLSearchParams();

    if (params.productKey) {
      query.set("product_key", String(params.productKey).trim());
    }
    if (params.ean) {
      query.set("ean", String(params.ean).trim());
    }
    if (params.q) {
      query.set("q", String(params.q).trim());
    }
    if (params.source) {
      query.set("source", String(params.source));
    }
    if (params.sku) {
      query.set("sku", String(params.sku));
    }

    const suffix = query.toString();
    return `./compare.html${suffix ? `?${suffix}` : ""}`;
  }

  function buildCompareHref(product) {
    if (!product.product_key && !product.ean) {
      return "#";
    }

    return buildCompareUrl({
      productKey: product.product_key,
      ean: product.ean,
      source: product._catalogId,
      sku: product.sku,
    });
  }

  function buildImagePlaceholder(message = "Sin imagen") {
    return (
      "data:image/svg+xml;charset=UTF-8," +
      encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
          <rect width="400" height="400" fill="#f6e7d4"/>
          <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
           font-family="Arial, sans-serif" font-size="26" fill="#9f3512">${message}</text>
        </svg>`
      )
    );
  }

  function setLinkState(link, href, text, disabledClass) {
    if (!link) {
      return;
    }

    if (text !== null && text !== undefined) {
      link.textContent = text;
    }
    link.href = href || "#";
    link.classList.toggle(disabledClass, !href || href === "#");

    if (!href || href === "#") {
      link.setAttribute("aria-disabled", "true");
      link.addEventListener(
        "click",
        (event) => {
          event.preventDefault();
        },
        { once: true }
      );
      return;
    }

    link.removeAttribute("aria-disabled");
  }

  function fillProductCard(card, product, options = {}) {
    const {
      compareHref = buildCompareHref(product),
      compareText = "Comparar",
      productText = "Ver producto",
      showCompare = true,
      highlightOrigin = false,
    } = options;

    const imageLink = card.querySelector(".product-image-link");
    const image = card.querySelector(".product-image");
    const category = card.querySelector(".product-category");
    const chain = card.querySelector(".product-store");
    const name = card.querySelector(".product-name");
    const brand = card.querySelector(".product-brand");
    const measure = card.querySelector(".product-measure");
    const unitPrice = card.querySelector(".product-unit-price");
    const sku = card.querySelector(".product-sku");
    const price = card.querySelector(".product-price");
    const listPrice = card.querySelector(".product-list-price");
    const ean = card.querySelector(".product-ean");
    const compareLink = card.querySelector(".compare-link");
    const productLink = card.querySelector(".product-link");

    card.classList.toggle("is-origin-product", Boolean(highlightOrigin));
    card.dataset.catalogId = product._catalogId || "";
    card.dataset.ean = product.ean || "";

    setLinkState(imageLink, product.link, null, "is-disabled");
    setLinkState(productLink, product.link, productText, "is-disabled");

    image.src = product.image || buildImagePlaceholder();
    image.alt = product.name || "Producto";
    image.addEventListener(
      "error",
      () => {
        image.src = buildImagePlaceholder();
      },
      { once: true }
    );

    if (compareLink) {
      compareLink.style.display = showCompare ? "inline-flex" : "none";
      if (showCompare) {
        setLinkState(compareLink, compareHref, compareText, "is-disabled");
      }
    }

    category.textContent = product.category || "Sin categoria";
    chain.textContent = product._catalogShortLabel || product._catalogLabel || product.chain || "-";
    name.textContent = product.name || "Sin nombre";
    brand.textContent = product.brand || "Marca no disponible";
    measure.textContent =
      product.quantity && product.unit
        ? `${product.quantity} ${product.unit}`
        : "Medida no disponible";
    if (unitPrice) {
      unitPrice.textContent = formatUnitPrice(product);
    }
    sku.textContent = `SKU ${product.sku || "-"}`;
    price.textContent = formatCurrency(product.price);

    if (Number(product.list_price || 0) > Number(product.price || 0)) {
      listPrice.textContent = formatCurrency(product.list_price);
      listPrice.style.display = "inline";
    } else {
      listPrice.textContent = "";
      listPrice.style.display = "none";
    }

    ean.textContent = product.ean ? `EAN ${product.ean}` : "EAN no disponible";
  }

  window.PriceScrapperData = {
    buildCompareHref,
    buildCompareUrl,
    fillProductCard,
    formatCurrency,
    formatUnitPrice,
    getUnitPrice,
    loadCatalogBundles,
    loadProductCatalog,
    loadProductComparison,
    normalizeText,
    prepareCatalogProducts,
    prepareProductsFromBundle,
  };
})();
