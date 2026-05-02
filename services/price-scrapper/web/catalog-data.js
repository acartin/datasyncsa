(function () {
  const OUTPUTS = [
    {
      id: "walmart_cr_catalog",
      label: "Walmart Costa Rica",
      shortLabel: "Walmart",
      store: "walmart_cr",
      catalogSources: [
        "../output/walmart_cr_abarrotes/catalog.json",
        "/output/walmart_cr_abarrotes/catalog.json",
      ],
      metadataSources: [
        "../output/walmart_cr_abarrotes/metadata.json",
        "/output/walmart_cr_abarrotes/metadata.json",
      ],
    },
    {
      id: "maxi_pali_cr_catalog",
      label: "Maxi Palí Costa Rica",
      shortLabel: "Maxi Palí",
      store: "maxi_pali_cr",
      catalogSources: [
        "../output/maxi_pali_abarrotes/catalog.json",
        "/output/maxi_pali_abarrotes/catalog.json",
      ],
      metadataSources: [
        "../output/maxi_pali_abarrotes/metadata.json",
        "/output/maxi_pali_abarrotes/metadata.json",
      ],
    },
    {
      id: "masxmenos_cr_catalog",
      label: "Más x Menos Costa Rica",
      shortLabel: "Más x Menos",
      store: "masxmenos_cr",
      catalogSources: [
        "../output/masxmenos_cr_abarrotes/catalog.json",
        "/output/masxmenos_cr_abarrotes/catalog.json",
      ],
      metadataSources: [
        "../output/masxmenos_cr_abarrotes/metadata.json",
        "/output/masxmenos_cr_abarrotes/metadata.json",
      ],
    },
    {
      id: "megasuper_cr_catalog",
      label: "Megasuper Costa Rica",
      shortLabel: "Megasuper",
      store: "megasuper_cr",
      catalogSources: [
        "../output/megasuper_cr_abarrotes/catalog.json",
        "/output/megasuper_cr_abarrotes/catalog.json",
      ],
      metadataSources: [
        "../output/megasuper_cr_abarrotes/metadata.json",
        "/output/megasuper_cr_abarrotes/metadata.json",
      ],
    },
  ];

  async function loadJsonFromSources(sources, options = {}) {
    const { required = true } = options;
    let lastError = null;

    for (const source of sources) {
      try {
        const response = await fetch(source, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        return {
          data: await response.json(),
          source,
        };
      } catch (error) {
        lastError = error;
      }
    }

    if (!required) {
      return {
        data: null,
        source: null,
        error: lastError,
      };
    }

    throw new Error(
      `No se pudo cargar ninguna fuente. Detalle: ${lastError?.message || "sin detalle"}`
    );
  }

  async function loadCatalogBundles() {
    const results = await Promise.allSettled(
      OUTPUTS.map(async (output) => {
        const catalog = await loadJsonFromSources(output.catalogSources);
        if (!Array.isArray(catalog.data)) {
          throw new Error(`La salida ${output.label} no devolvio un arreglo JSON.`);
        }

        const metadataResult = await loadJsonFromSources(output.metadataSources, {
          required: false,
        });

        const metadata =
          metadataResult.data && typeof metadataResult.data === "object"
            ? metadataResult.data
            : null;

        return {
          ...output,
          id: metadata?.catalog_id || output.id,
          label: metadata?.display_name || output.label,
          shortLabel: metadata?.short_label || output.shortLabel,
          source: catalog.source,
          products: catalog.data,
          metadata,
        };
      })
    );

    const bundles = [];
    const failures = [];

    results.forEach((result, index) => {
      const output = OUTPUTS[index];
      if (result.status === "fulfilled") {
        bundles.push(result.value);
        return;
      }

      failures.push({
        ...output,
        error: result.reason,
      });
    });

    return { bundles, failures };
  }

  function normalizeText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
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

  function buildSearchIndex(product) {
    return normalizeText(
      [
        product.name,
        product.brand,
        product.category,
        product.ean,
        product.sku,
        product.product_id,
        product._catalogLabel,
        product._catalogShortLabel,
      ].join(" ")
    );
  }

  function normalizeCanonicalProduct(product) {
    return {
      ...product,
      store: product.store?.store_id || "",
      product_id: product.identity?.product_id || "",
      sku: product.identity?.sku || "",
      name: product.content?.name || "",
      brand: product.identity?.brand || "",
      ean: product.identity?.ean || null,
      price: product.pricing?.price ?? null,
      list_price: product.pricing?.list_price ?? null,
      has_discount: Boolean(product.pricing?.has_discount),
      unit: product.measurement?.unit || null,
      quantity: product.measurement?.quantity ?? null,
      category: product.taxonomy?.category_path || "",
      link: product.content?.link || null,
      image: product.content?.image || null,
      pricing_scope: product.pricing_scope || null,
      _canonical: product,
    };
  }

  function normalizeProductRecord(product) {
    if (product && product.schema_version === "canonical_product_v1") {
      return normalizeCanonicalProduct(product);
    }

    return { ...product };
  }

  function prepareProductsFromBundle(bundle) {
    return bundle.products.map((product) => {
      const normalized = normalizeProductRecord(product);
      const prepared = {
        ...normalized,
        _catalogId: bundle.id,
        _catalogLabel: bundle.label,
        _catalogShortLabel: bundle.shortLabel,
        _catalogSource: bundle.source,
        _generatedAt: bundle.metadata?.generated_at || null,
      };
      prepared._searchIndex = buildSearchIndex(prepared);
      return prepared;
    });
  }

  function buildCompareUrl(params = {}) {
    const query = new URLSearchParams();

    if (params.ean) {
      query.set("ean", String(params.ean).trim());
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
    if (!product.ean) {
      return "#";
    }

    return buildCompareUrl({
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
    const store = card.querySelector(".product-store");
    const name = card.querySelector(".product-name");
    const brand = card.querySelector(".product-brand");
    const measure = card.querySelector(".product-measure");
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
    store.textContent = product._catalogShortLabel || product._catalogLabel || product.store || "-";
    name.textContent = product.name || "Sin nombre";
    brand.textContent = product.brand || "Marca no disponible";
    measure.textContent =
      product.quantity && product.unit
        ? `${product.quantity} ${product.unit}`
        : "Medida no disponible";
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
    OUTPUTS,
    buildCompareHref,
    buildCompareUrl,
    fillProductCard,
    formatCurrency,
    loadCatalogBundles,
    normalizeText,
    prepareProductsFromBundle,
  };
})();
