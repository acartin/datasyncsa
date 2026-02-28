function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function normalizeValue(value) {
    if (value === null || value === undefined || value === '') return '-';
    if (typeof value === 'object') {
        try {
            return JSON.stringify(value, null, 2);
        } catch (_error) {
            return String(value);
        }
    }
    return String(value);
}

function isMissingValue(value) {
    const normalized = normalizeValue(value).trim();
    return normalized === '' || normalized === '-';
}

function isSafeHttpUrl(value) {
    try {
        const parsed = new URL(String(value));
        return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch (_error) {
        return false;
    }
}

function compactUrl(value) {
    try {
        const parsed = new URL(String(value));
        const compactPath = parsed.pathname && parsed.pathname !== '/' ? parsed.pathname : '';
        return `${parsed.hostname}${compactPath}`.slice(0, 88);
    } catch (_error) {
        return String(value);
    }
}

function renderValue(item) {
    const rawValue = normalizeValue(item.value);
    const safeValue = escapeHtml(rawValue);
    const kind = String(item.kind || 'text');

    if (isMissingValue(rawValue)) {
        return '<span class="source-origin-empty">No disponible</span>';
    }

    if (kind === 'url' && isSafeHttpUrl(rawValue)) {
        const compact = escapeHtml(compactUrl(rawValue));
        const href = escapeHtml(rawValue);
        return `<a class="source-origin-link" href="${href}" target="_blank" rel="noopener noreferrer">${compact}</a>`;
    }

    if (kind === 'json') {
        return `<pre class="source-origin-pre mb-0">${safeValue}</pre>`;
    }

    if (kind === 'mono') {
        return `<code class="source-origin-code">${safeValue}</code>`;
    }

    return `<span>${safeValue}</span>`;
}

function normalizeItems(source) {
    if (!Array.isArray(source)) return [];
    return source
        .filter((item) => item && typeof item === 'object')
        .map((item) => ({
            key: String(item.key || ''),
            label: String(item.label || item.key || 'Dato'),
            value: item.value,
            icon: String(item.icon || 'ri-information-line'),
            kind: String(item.kind || 'text'),
        }));
}

function renderRows(items) {
    if (!items.length) {
        return '<div class="source-origin-empty-row">Sin datos disponibles.</div>';
    }
    return items.map((item) => `
        <div class="source-origin-row">
            <div class="source-origin-row-icon"><i class="${escapeHtml(item.icon)}"></i></div>
            <div class="source-origin-row-label">${escapeHtml(item.label)}</div>
            <div class="source-origin-row-value">${renderValue(item)}</div>
        </div>
    `).join('');
}

export function LinkLeadSourceView(component) {
    const props = component.properties || {};
    const sourceLabel = escapeHtml(normalizeValue(props.source_label || 'Sin fuente'));
    const sourceIcon = escapeHtml(String(props.source_icon || 'ri-links-line'));
    const businessDomain = normalizeValue(props.business_domain || '-');
    const clickId = normalizeValue(props.click_id || '-');
    const clickIdType = normalizeValue(props.click_id_type || '-');

    const utmItems = normalizeItems(props.utm_items);
    const originItems = normalizeItems(props.origin_items);
    const technicalItems = normalizeItems(props.technical_items);

    return `
        <div class="source-origin-view">
            <section class="source-origin-hero">
                <div class="source-origin-hero-main">
                    <div class="source-origin-hero-icon"><i class="${sourceIcon}"></i></div>
                    <div class="source-origin-hero-text">
                        <h5 class="source-origin-hero-title mb-1">Fuente de captacion</h5>
                        <div class="source-origin-hero-subtitle">${sourceLabel}</div>
                    </div>
                </div>
                <div class="source-origin-hero-meta">
                    <span class="source-origin-chip"><i class="ri-fingerprint-line"></i>${escapeHtml(clickId)}</span>
                    <span class="source-origin-chip"><i class="ri-price-tag-2-line"></i>${escapeHtml(clickIdType)}</span>
                    <span class="source-origin-chip"><i class="ri-global-line"></i>${escapeHtml(businessDomain)}</span>
                </div>
            </section>

            <div class="source-origin-grid">
                <section class="source-origin-card">
                    <h6 class="source-origin-title">UTM Attribution</h6>
                    <div class="source-origin-body">
                        ${renderRows(utmItems)}
                    </div>
                </section>

                <section class="source-origin-card">
                    <h6 class="source-origin-title">Origen del enlace</h6>
                    <div class="source-origin-body">
                        ${renderRows(originItems)}
                    </div>
                </section>

                <section class="source-origin-card source-origin-card-wide">
                    <h6 class="source-origin-title">Contexto tecnico</h6>
                    <div class="source-origin-body">
                        ${renderRows(technicalItems)}
                    </div>
                </section>
            </div>
        </div>
    `;
}
