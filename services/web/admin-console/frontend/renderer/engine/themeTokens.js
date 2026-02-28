const THERMAL_TOKEN_MAP = {
    'thermal-extreme': 'var(--ac-thermal-extreme)',
    'thermal-high': 'var(--ac-thermal-high)',
    'thermal-mid': 'var(--ac-thermal-mid)',
    'thermal-low': 'var(--ac-thermal-low)',
    'thermal-none': 'var(--ac-thermal-none)',
    'thermal-info': 'var(--ac-thermal-info)'
};

const BOOTSTRAP_TOKEN_MAP = {
    primary: 'var(--vz-primary)',
    secondary: 'var(--vz-secondary)',
    success: 'var(--vz-success)',
    info: 'var(--vz-info)',
    warning: 'var(--vz-warning)',
    danger: 'var(--vz-danger)',
    light: 'var(--vz-light)',
    dark: 'var(--vz-dark)'
};

const DYNAMIC_STYLE_TAG_ID = 'ac-dynamic-style-registry';
const dynamicClassCache = new Map();

function djb2Hash(input) {
    let hash = 5381;
    for (let i = 0; i < input.length; i += 1) {
        hash = ((hash << 5) + hash) ^ input.charCodeAt(i);
    }
    return (hash >>> 0).toString(36);
}

function getDynamicStyleSheet() {
    if (typeof document === 'undefined') return null;
    let styleTag = document.getElementById(DYNAMIC_STYLE_TAG_ID);
    if (!styleTag) {
        styleTag = document.createElement('style');
        styleTag.id = DYNAMIC_STYLE_TAG_ID;
        document.head.appendChild(styleTag);
    }
    return styleTag.sheet || null;
}

export function isCssColor(value) {
    if (typeof value !== 'string') return false;
    const normalized = value.trim().toLowerCase();
    return (
        normalized.startsWith('#') ||
        normalized.startsWith('rgb(') ||
        normalized.startsWith('rgba(') ||
        normalized.startsWith('hsl(') ||
        normalized.startsWith('hsla(') ||
        normalized.startsWith('var(')
    );
}

export function resolveUiColor(rawColor, fallback = 'var(--ac-color-neutral)') {
    if (isCssColor(rawColor)) return rawColor;
    const key = String(rawColor || '').trim().toLowerCase();
    if (!key) return fallback;
    if (THERMAL_TOKEN_MAP[key]) return THERMAL_TOKEN_MAP[key];
    if (BOOTSTRAP_TOKEN_MAP[key]) return BOOTSTRAP_TOKEN_MAP[key];
    return fallback;
}

export function resolveScoreTierColor(scoreTenScale) {
    const score = Number(scoreTenScale);
    if (!Number.isFinite(score)) return 'var(--ac-score-none)';
    if (score >= 8) return 'var(--ac-score-high)';
    if (score >= 4) return 'var(--ac-score-medium)';
    return 'var(--ac-score-low)';
}

export function resolveGaugeRampColor(normalizedValue) {
    const normalized = Number(normalizedValue);
    if (!Number.isFinite(normalized)) return 'var(--ac-color-neutral)';
    if (normalized >= 0.9) return 'var(--ac-thermal-extreme)';
    if (normalized >= 0.7) return 'var(--ac-thermal-high)';
    if (normalized >= 0.5) return 'var(--ac-thermal-mid)';
    if (normalized >= 0.2) return 'var(--ac-thermal-low)';
    return 'var(--ac-color-neutral)';
}

export function resolveGaugeRampColorFrom100(scoreHundredScale) {
    const score = Number(scoreHundredScale);
    if (!Number.isFinite(score)) return 'var(--ac-color-neutral)';
    const normalized = Math.max(0, Math.min(100, score)) / 100;
    return resolveGaugeRampColor(normalized);
}

export function ensureDynamicClass(prefix, cssDeclarationBody) {
    const safePrefix = String(prefix || 'ac').replace(/[^a-z0-9_-]/gi, '').toLowerCase() || 'ac';
    const body = String(cssDeclarationBody || '').trim();
    if (!body) return '';

    const cacheKey = `${safePrefix}|${body}`;
    const cached = dynamicClassCache.get(cacheKey);
    if (cached) return cached;

    const className = `${safePrefix}-${djb2Hash(cacheKey)}`;
    const sheet = getDynamicStyleSheet();
    if (sheet) {
        try {
            sheet.insertRule(`.${className}{${body}}`, sheet.cssRules.length);
        } catch (_error) {
            return '';
        }
    }

    dynamicClassCache.set(cacheKey, className);
    return className;
}
