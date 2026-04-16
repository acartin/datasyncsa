import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

class PropertyCard extends LitElement {
  static properties = {
    propertyId: { type: String, attribute: 'property-id' },
    title: { type: String },
    price: { type: Number },
    currency: { type: String },
    priceNote: { type: String, attribute: 'price-note' },
    location: { type: String },
    imageUrl: { type: String },
    imageUrls: { type: Array },
    photoCount: { type: Number },
    publicUrl: { type: String },
    features: { type: Object },
    tags: { type: Array },
    stats: { type: Array },
    bedrooms: { type: Object },
    bathrooms: { type: Object },
    sqm: { type: Object },
    garage: { type: Object },
    amenities: { type: Array },
    description: { type: String },
    badgeMain: { type: String, attribute: 'badge-main' },
    badgeSub: { type: String, attribute: 'badge-sub' },
    quickActions: { type: Array },
  };

  static styles = css`
    :host {
      display: block;
      width: 100%;
      color: var(--text-on-surface, #f8fafc);
      font-family: var(--font-body, 'DM Sans', sans-serif);
      --hm-line: rgba(42, 58, 82, 0.18);
      --hm-line-strong: rgba(42, 58, 82, 0.24);
      --hm-surface-soft: rgba(42, 58, 82, 0.038);
      --hm-surface-pill: rgba(42, 58, 82, 0.06);
      --hm-text-soft: #6b7f9c;
    }

    .hm-root {
      width: 100%;
      max-width: 380px;
      padding: 4px 0 8px;
    }

    .hm-card {
      overflow: hidden;
      border-radius: 20px;
      border: 1px solid var(--hm-line);
      background: color-mix(in srgb, var(--brand-surface, #0f172a) 84%, transparent);
      transition:
        transform 0.45s cubic-bezier(0.23, 1, 0.32, 1),
        box-shadow 0.45s ease,
        border-color 0.25s ease;
    }

    .hm-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 20px 48px rgba(0, 0, 0, 0.28);
      border-color: var(--hm-line-strong);
    }

    .hm-img-wrap {
      position: relative;
      height: 220px;
      overflow: hidden;
      background: #0d1117;
    }

    .hm-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform 0.6s cubic-bezier(0.23, 1, 0.32, 1);
    }

    .hm-card:hover .hm-img {
      transform: scale(1.05);
    }

    .hm-img-placeholder {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(145deg, #0d1117 0%, #1a1f35 45%, #0d2137 100%);
      transition: transform 0.6s cubic-bezier(0.23, 1, 0.32, 1);
    }

    .hm-card:hover .hm-img-placeholder {
      transform: scale(1.04);
    }

    .hm-img-icon {
      opacity: 0.07;
    }

    .hm-scrim {
      position: absolute;
      inset: 0;
      background: linear-gradient(
        to top,
        rgba(0, 0, 0, 0.75) 0%,
        rgba(0, 0, 0, 0.08) 55%,
        transparent 100%
      );
      pointer-events: none;
    }

    .hm-badges {
      position: absolute;
      top: 14px;
      left: 14px;
      z-index: 2;
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      max-width: calc(100% - 28px);
    }

    .hm-badge {
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 10.5px;
      font-weight: 500;
      letter-spacing: 0.04em;
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
    }

    .hm-badge-main {
      background: rgba(16, 185, 129, 0.88);
      color: #fff;
    }

    .hm-badge-sub {
      background: rgba(255, 255, 255, 0.13);
      color: rgba(255, 255, 255, 0.9);
      border: 0.5px solid rgba(255, 255, 255, 0.22);
    }

    .hm-img-bottom {
      position: absolute;
      left: 16px;
      right: 16px;
      bottom: 14px;
      z-index: 2;
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 12px;
    }

    .hm-price {
      color: #fff;
      font-family: var(--font-heading, 'Cormorant Garamond', serif);
      font-size: 30px;
      font-weight: 600;
      line-height: 1;
      text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    }

    .hm-price-note {
      margin-top: 3px;
      color: rgba(255, 255, 255, 0.6);
      font-family: var(--font-body, 'DM Sans', sans-serif);
      font-size: 11px;
    }

    .hm-photo-pill {
      display: flex;
      align-items: center;
      gap: 5px;
      flex: none;
      padding: 5px 10px;
      border-radius: 999px;
      background: rgba(0, 0, 0, 0.48);
      color: rgba(255, 255, 255, 0.8);
      font-size: 11px;
      white-space: nowrap;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
    }

    .hm-photo-pill svg {
      width: 13px;
      height: 13px;
      fill: rgba(255, 255, 255, 0.7);
    }

    .hm-body {
      padding: 18px 18px 16px;
    }

    .hm-title {
      margin-bottom: 5px;
      color: var(--text-on-surface, #f8fafc);
      font-family: var(--font-heading, 'Cormorant Garamond', serif);
      font-size: 21px;
      font-weight: 600;
      line-height: 1.2;
    }

    .hm-location {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-bottom: 16px;
      color: var(--text-muted, #94a3b8);
      font-size: 12.5px;
    }

    .hm-location svg {
      width: 11px;
      height: 11px;
      fill: currentColor;
      flex-shrink: 0;
    }

    .hm-stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      margin-bottom: 14px;
      overflow: hidden;
      border: 1px solid var(--hm-line);
      border-radius: 12px;
      background: var(--hm-surface-soft);
    }

    .hm-stat {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 3px;
      padding: 11px 0;
    }

    .hm-stat:not(:last-child)::after {
      content: '';
      position: absolute;
      top: 18%;
      right: 0;
      width: 0.5px;
      height: 64%;
      background: var(--hm-line);
    }

    .hm-stat-icon {
      width: 15px;
      height: 15px;
      fill: var(--text-muted, #94a3b8);
    }

    .hm-stat-val {
      color: var(--text-on-surface, #f8fafc);
      font-size: 15px;
      font-weight: 500;
      line-height: 1;
    }

    .hm-stat-lbl {
      color: var(--text-muted, #94a3b8);
      font-size: 10px;
      letter-spacing: 0.01em;
      text-align: center;
    }

    .hm-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .hm-tag {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 5px 12px;
      border-radius: 10px;
      border: 1px solid var(--hm-line);
      background: var(--hm-surface-pill);
      color: var(--hm-text-soft);
      font-size: 11px;
      font-weight: 400;
    }

    .hm-footer {
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 6px 18px 18px;
      justify-content: flex-start;
      flex-wrap: wrap;
    }

    .hm-footer::before {
      content: '';
      display: block;
      width: 100%;
      border-top: 1px solid var(--hm-line);
    }

    .hm-quick-actions {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      padding: 0 18px 10px;
    }

    .hm-chip {
      min-height: 42px;
      border: 1px solid var(--hm-line-strong);
      background: rgba(42, 58, 82, 0.07);
      color: var(--text-on-surface, #f8fafc);
      border-radius: 999px;
      padding: 8px 12px;
      font-family: var(--font-body, 'DM Sans', sans-serif);
      font-size: 12px;
      font-weight: 600;
      line-height: 1.2;
      cursor: pointer;
      transition: background 0.2s ease, color 0.2s ease, transform 0.15s ease;
    }

    .hm-chip:first-child {
      background: rgba(248, 250, 252, 0.14);
      border-color: rgba(248, 250, 252, 0.22);
    }

    .hm-chip:hover {
      background: rgba(248, 250, 252, 0.18);
      transform: translateY(-1px);
    }

    .hm-chip:active {
      transform: scale(0.98);
    }

    .hm-link-btn {
      padding: 0;
      border: none;
      background: transparent;
      color: var(--hm-text-soft);
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-body, 'DM Sans', sans-serif);
      font-size: 12px;
      font-weight: 500;
      transition: color 0.2s ease, transform 0.15s ease;
    }

    .hm-link-btn svg {
      width: 12px;
      height: 12px;
      fill: currentColor;
    }

    .hm-link-btn:hover {
      color: var(--text-on-surface, #f8fafc);
      transform: translateY(-1px);
    }

    .hm-link-btn:active {
      transform: scale(0.98);
    }

    @media (max-width: 480px) {
      .hm-root {
        max-width: 100%;
      }

      .hm-img-wrap {
        height: 190px;
      }

      .hm-title {
        font-size: 18px;
      }

      .hm-price {
        font-size: 26px;
      }

      .hm-tag {
        min-height: 30px;
        padding: 6px 13px;
        border-radius: 10px;
        border-color: var(--hm-line-strong);
        background: rgba(42, 58, 82, 0.075);
        color: #647792;
        font-size: 12.5px;
        font-weight: 500;
      }

      .hm-quick-actions {
        grid-template-columns: 1fr;
      }

      .hm-link-btn {
        font-size: 13px;
        font-weight: 600;
      }

      .hm-link-btn svg {
        width: 14px;
        height: 14px;
        opacity: 0.92;
      }
    }
  `;

  constructor() {
    super();
    this.title = '';
    this.propertyId = '';
    this.price = 0;
    this.currency = 'USD';
    this.priceNote = '';
    this.location = '';
    this.imageUrl = '';
    this.imageUrls = [];
    this.photoCount = 0;
    this.publicUrl = '';
    this.features = {};
    this.tags = [];
    this.stats = [];
    this.bedrooms = null;
    this.bathrooms = null;
    this.sqm = null;
    this.garage = null;
    this.amenities = [];
    this.description = '';
    this.badgeMain = '';
    this.badgeSub = '';
    this.quickActions = [];
  }

  _normalizedFeatures() {
    return this.features && typeof this.features === 'object' && !Array.isArray(this.features)
      ? this.features
      : {};
  }

  _firstNonEmpty(...values) {
    for (const value of values) {
      if (value == null) {
        continue;
      }
      if (Array.isArray(value)) {
        if (value.length > 0) {
          return value;
        }
        continue;
      }
      if (typeof value === 'string') {
        const cleaned = value.trim();
        if (cleaned) {
          return cleaned;
        }
        continue;
      }
      return value;
    }
    return null;
  }

  _normalizeList(...sources) {
    const seen = new Set();
    const values = [];

    const push = (rawValue) => {
      if (rawValue == null) {
        return;
      }
      const value = String(rawValue).trim();
      if (!value) {
        return;
      }
      const key = value.toLowerCase();
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      values.push(value);
    };

    sources.forEach((source) => {
      if (Array.isArray(source)) {
        source.forEach(push);
        return;
      }
      if (typeof source === 'string') {
        source.split(',').forEach(push);
      }
    });

    return values;
  }

  _formatNumericValue(value, decimals = 0) {
    if (value == null || value === '') {
      return null;
    }

    if (typeof value === 'number' && Number.isFinite(value)) {
      return decimals > 0 ? value.toFixed(decimals) : String(Math.round(value));
    }

    const cleaned = String(value).trim();
    if (!cleaned) {
      return null;
    }

    if (/^\d+([.,]\d+)?$/.test(cleaned)) {
      return cleaned.replace(',', '.');
    }

    return cleaned;
  }

  _formatBathrooms(value) {
    if (value == null || value === '') {
      return null;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return Number.isInteger(value) ? String(value) : value.toFixed(1);
    }
    const cleaned = String(value).trim();
    return cleaned || null;
  }

  _formatArea(value) {
    if (value == null || value === '') {
      return null;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return String(Math.round(value));
    }
    const cleaned = String(value)
      .replace(/m2|m²|sqm|sq\.?\s?m/gi, '')
      .trim();
    return cleaned || null;
  }

  _coerceNumber(value) {
    if (value == null || value === '') {
      return null;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    const cleaned = String(value).replace(/[^0-9.,-]/g, '').replace(',', '.');
    if (!cleaned) {
      return null;
    }
    const parsed = Number(cleaned);
    return Number.isFinite(parsed) ? parsed : null;
  }

  _formatPrice() {
    const currency = String(this.currency || this._normalizedFeatures().currency || 'USD').trim().toUpperCase() || 'USD';
    try {
      return new Intl.NumberFormat('es-CR', {
        style: 'currency',
        currency,
        maximumFractionDigits: 0,
      }).format(this.price || 0);
    } catch (_) {
      return new Intl.NumberFormat('es-CR', {
        maximumFractionDigits: 0,
      }).format(this.price || 0);
    }
  }

  _derivePriceNote() {
    const features = this._normalizedFeatures();
    const explicit = this._firstNonEmpty(this.priceNote, features.price_note);
    if (explicit) {
      return explicit;
    }

    const listingType = String(
      this._firstNonEmpty(
        features.listing_type,
        features.operation,
        features.operation_type,
      ) || ''
    ).toLowerCase();

    if (/(alquiler|renta|rent)/.test(listingType)) {
      return 'Precio de alquiler';
    }
    if (/(venta|sale)/.test(listingType)) {
      return 'Precio de venta';
    }
    return 'Precio publicado';
  }

  _titleize(value) {
    if (!value) {
      return '';
    }
    return String(value)
      .trim()
      .replace(/_/g, ' ')
      .replace(/\s+/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  _normalizeBadge(value) {
    const label = this._titleize(value);
    if (!label) {
      return '';
    }
    const normalized = label.toLowerCase();
    return normalized === 'default' || normalized.startsWith('default ') ? '' : label;
  }

  _deriveBadgeMain() {
    const features = this._normalizedFeatures();
    const explicit = this._normalizeBadge(this._firstNonEmpty(this.badgeMain, features.badge_main));
    if (explicit) {
      return explicit;
    }
    if (features.is_featured) {
      return 'Destacada';
    }
    return '';
  }

  _deriveBadgeSub() {
    const features = this._normalizedFeatures();
    return this._normalizeBadge(
      this._firstNonEmpty(
        this.badgeSub,
        features.badge_sub,
        features.listing_type,
        features.property_type,
      )
    );
  }

  _derivePhotoCount() {
    const explicit = Number(this.photoCount);
    if (Number.isFinite(explicit) && explicit > 0) {
      return explicit;
    }
    const images = Array.isArray(this.imageUrls) ? this.imageUrls.filter(Boolean) : [];
    if (images.length > 0) {
      return images.length;
    }
    return this.imageUrl ? 1 : 0;
  }

  _deriveLocation() {
    const features = this._normalizedFeatures();
    return this._firstNonEmpty(
      this.location,
      features.address,
      features.neighborhood,
      features.city,
      features.province,
      ''
    );
  }

  _deriveTags() {
    const features = this._normalizedFeatures();
    return this._normalizeList(
      this.tags,
      this.amenities,
      features.highlights,
      features.amenities,
    ).slice(0, 2);
  }

  _isLikelyLand(features) {
    const hints = [
      this.title,
      features.property_type,
      features.land_use,
      features.use,
      features.tipo,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    if (/(terreno|lote|lot|land|solar)/.test(hints)) {
      return true;
    }
    const hasLotArea = this._firstNonEmpty(features.lot_size_sqm, features.lotSizeSqm);
    const bedrooms = this._coerceNumber(this._firstNonEmpty(this.bedrooms, features.bedrooms_clean, features.bedrooms));
    const bathrooms = this._coerceNumber(this._firstNonEmpty(this.bathrooms, features.bathrooms_clean, features.bathrooms));
    return Boolean(hasLotArea) && !(bedrooms > 0) && !(bathrooms > 0);
  }

  _normalizeStats() {
    if (Array.isArray(this.stats)) {
      const explicit = this.stats
        .map((item) => {
          if (!item || typeof item !== 'object') {
            return null;
          }
          const icon = String(item.icon || '').trim().toLowerCase();
          const value = String(item.value || '').trim();
          const label = String(item.label || '').trim();
          if (!icon || !value || !label) {
            return null;
          }
          return { icon, value, label };
        })
        .filter(Boolean)
        .slice(0, 3);
      if (explicit.length) {
        return explicit;
      }
    }

    const features = this._normalizedFeatures();
    const isLand = this._isLikelyLand(features);
    const stats = [];

    if (isLand) {
      const lotArea = this._formatArea(this._firstNonEmpty(features.lot_size_sqm, features.lotSizeSqm, this.sqm, features.sqm_clean));
      const front = this._firstNonEmpty(features.front, features.frente, features.frontage, features.frontage_m);
      const landUse = this._firstNonEmpty(features.land_use, features.uso_suelo, features.use);

      if (lotArea) {
        stats.push({ icon: 'area', value: lotArea, label: 'm² terreno' });
      }
      if (front) {
        const normalizedFront = /[a-z]/i.test(String(front)) ? String(front).trim() : `${this._formatNumericValue(front) || front}m`;
        stats.push({ icon: 'front', value: normalizedFront, label: 'Frente' });
      }
      if (landUse) {
        stats.push({ icon: 'use', value: String(landUse).trim(), label: 'Uso suelo' });
      }
      if (stats.length) {
        return stats.slice(0, 3);
      }
    }

    const beds = this._formatNumericValue(this._firstNonEmpty(this.bedrooms, features.bedrooms_clean, features.bedrooms));
    const baths = this._formatBathrooms(this._firstNonEmpty(this.bathrooms, features.bathrooms_clean, features.bathrooms));
    const area = this._formatArea(this._firstNonEmpty(this.sqm, features.sqm_clean, features.sqm, features.area_display, features.lot_size_sqm));
    const garage = this._formatNumericValue(this._firstNonEmpty(this.garage, features.garage_clean, features.garage));

    if (beds && this._coerceNumber(beds) > 0) {
      stats.push({ icon: 'bed', value: beds, label: 'Hab.' });
    }
    if (baths && this._coerceNumber(baths) > 0) {
      stats.push({ icon: 'bath', value: baths, label: 'Baños' });
    }
    if (area) {
      const label = features.lot_size_sqm && !this._firstNonEmpty(this.sqm, features.sqm_clean) ? 'm² terreno' : 'm² constr.';
      stats.push({ icon: 'area', value: area, label });
    }
    if (garage && this._coerceNumber(garage) > 0) {
      stats.push({ icon: 'garage', value: garage, label: 'Parqueos' });
    }

    return stats.slice(0, 3);
  }

  _renderStatIcon(icon) {
    switch (String(icon || '').trim().toLowerCase()) {
      case 'bed':
        return html`<svg class="hm-stat-icon" viewBox="0 0 24 24"><path d="M7 13c1.66 0 3-1.34 3-3S8.66 7 7 7s-3 1.34-3 3 1.34 3 3 3zm12-6h-8v7H3V5H1v15h2v-3h18v3h2v-9c0-2.21-1.79-4-4-4z"></path></svg>`;
      case 'bath':
        return html`<svg class="hm-stat-icon" viewBox="0 0 24 24"><path d="M7 6h2V4H7v2zm0 4h2V8H7v2zm4-4h2V4h-2v2zm0 4h2V8h-2v2zm-8 4h18v2H3v-2zm2 4h14v2H5v-2zm-2-8h2v-1c0-.55.45-1 1-1h10c.55 0 1 .45 1 1v1h2v-1c0-1.65-1.35-3-3-3H5C3.35 9 2 10.35 2 12v1z"></path></svg>`;
      case 'garage':
        return html`<svg class="hm-stat-icon" viewBox="0 0 24 24"><path d="M5 11l7-6 7 6v9h-2v-2H7v2H5v-9zm3 5h8v-4H8v4zm2-9h4l-2-1.71L10 7z"></path></svg>`;
      case 'front':
        return html`<svg class="hm-stat-icon" viewBox="0 0 24 24"><path d="M4 6h16v2H4V6zm0 10h16v2H4v-2zm2-7h2v6H6V9zm10 0h2v6h-2V9zm-5 0h2v6h-2V9z"></path></svg>`;
      case 'use':
        return html`<svg class="hm-stat-icon" viewBox="0 0 24 24"><path d="M3 5h18v2H3V5zm2 4h14v10H5V9zm3 2v6h2v-6H8zm4 0v6h2v-6h-2z"></path></svg>`;
      case 'area':
      default:
        return html`<svg class="hm-stat-icon" viewBox="0 0 24 24"><path d="M3 3v18h18V3H3zm16 16H5V5h14v14z"></path></svg>`;
    }
  }

  _normalizedQuickActions() {
    if (!Array.isArray(this.quickActions)) {
      return [];
    }
    return this.quickActions
      .map((item) => {
        if (!item || typeof item !== 'object') {
          return null;
        }
        const id = String(item.id || '').trim();
        const label = String(item.label || '').trim();
        const userText = String(item.user_text || item.userText || label).trim();
        if (!id || !label) {
          return null;
        }
        return { id, label, userText };
      })
      .filter(Boolean)
      .slice(0, 3);
  }

  _detailPrompt() {
    const propertyTitle = this._firstNonEmpty(this.title, 'esta propiedad');
    return typeof propertyTitle === 'string' && propertyTitle !== 'esta propiedad'
      ? `Quiero ver más detalles de ${propertyTitle}`
      : 'Quiero ver más detalles de esta propiedad';
  }

  _locationPrompt() {
    const propertyTitle = this._firstNonEmpty(this.title, 'esta propiedad');
    return typeof propertyTitle === 'string' && propertyTitle !== 'esta propiedad'
      ? `¿Dónde queda exactamente ${propertyTitle}?`
      : '¿Dónde queda exactamente esta propiedad?';
  }

  _emit(text) {
    if (typeof window.sendPrompt === 'function') {
      window.sendPrompt(text);
      return;
    }
    console.log('[property-card-v2] sendPrompt ->', text);
  }

  _emitQuickAction(action) {
    this.dispatchEvent(new CustomEvent('chat-action', {
      detail: {
        payload: {
          type: 'realtor_quick_action',
          actionId: action.id,
          actionLabel: action.label,
          userText: action.userText,
          propertyId: this.propertyId || null,
          title: this.title || null,
        }
      },
      bubbles: true,
      composed: true,
    }));
  }

  render() {
    const title = this._firstNonEmpty(this.title, 'Propiedad disponible');
    const location = this._deriveLocation();
    const features = this._normalizedFeatures();
    const badgeMain = this._deriveBadgeMain();
    const badgeSub = this._deriveBadgeSub();
    const photoCount = this._derivePhotoCount();
    const tags = this._deriveTags();
    const stats = this._normalizeStats();
    const quickActions = this._normalizedQuickActions();

    return html`
      <div class="hm-root">
        <article class="hm-card">
          <div class="hm-img-wrap">
            ${this.imageUrl
              ? html`<img class="hm-img" src=${this.imageUrl} alt=${title} loading="lazy">`
              : html`
                  <div class="hm-img-placeholder" aria-hidden="true">
                    <svg class="hm-img-icon" width="200" height="144" viewBox="0 0 220 160" fill="none">
                      <path d="M110 20 L200 80 L200 150 L20 150 L20 80 Z" fill="white"></path>
                      <path d="M20 80 L110 20 L200 80" fill="none" stroke="white" stroke-width="3"></path>
                      <rect x="85" y="95" width="50" height="55" fill="white" opacity="0.6"></rect>
                      <rect x="45" y="90" width="30" height="25" rx="2" fill="white" opacity="0.5"></rect>
                      <rect x="145" y="90" width="30" height="25" rx="2" fill="white" opacity="0.5"></rect>
                    </svg>
                  </div>
                `}

            <div class="hm-scrim"></div>

            ${(badgeMain || badgeSub)
              ? html`
                  <div class="hm-badges">
                    ${badgeMain ? html`<span class="hm-badge hm-badge-main">${badgeMain}</span>` : ''}
                    ${badgeSub ? html`<span class="hm-badge hm-badge-sub">${badgeSub}</span>` : ''}
                  </div>
                `
              : ''}

            <div class="hm-img-bottom">
              <div>
                <div class="hm-price">${this._formatPrice()}</div>
                <div class="hm-price-note">${this._derivePriceNote()}</div>
              </div>

              ${photoCount
                ? html`
                    <div class="hm-photo-pill">
                      <svg viewBox="0 0 24 24">
                        <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"></path>
                      </svg>
                      <span>${photoCount}</span> fotos
                    </div>
                  `
                : ''}
            </div>
          </div>

          <div class="hm-body">
            <div class="hm-title">${title}</div>

            ${location
              ? html`
                  <div class="hm-location">
                    <svg viewBox="0 0 24 24">
                      <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5S10.62 6.5 12 6.5s2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"></path>
                    </svg>
                    <span>${location}</span>
                  </div>
                `
              : ''}

            ${stats.length
              ? html`
                  <div class="hm-stats" style=${`grid-template-columns: repeat(${Math.min(stats.length, 3)}, minmax(0, 1fr));`}>
                    ${stats.map((stat) => html`
                      <div class="hm-stat">
                        ${this._renderStatIcon(stat.icon)}
                        <span class="hm-stat-val">${stat.value}</span>
                        <span class="hm-stat-lbl">${stat.label}</span>
                      </div>
                    `)}
                  </div>
                `
              : ''}

            ${tags.length
              ? html`
                  <div class="hm-tags">
                    ${tags.map((tag) => html`<span class="hm-tag">${tag}</span>`)}
                  </div>
                `
              : ''}
          </div>

          ${quickActions.length
            ? html`
                <div class="hm-quick-actions">
                  ${quickActions.map((action) => html`
                    <button class="hm-chip" type="button" @click=${() => this._emitQuickAction(action)}>
                      ${action.label}
                    </button>
                  `)}
                </div>
              `
            : ''}

          <div class="hm-footer">
            <button class="hm-link-btn" type="button" @click=${() => this._emit(this._detailPrompt())}>
              <svg viewBox="0 0 24 24">
                <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"></path>
              </svg>
              Ver detalles
            </button>
            <button class="hm-link-btn" type="button" @click=${() => this._emit(this._locationPrompt())}>
              <svg viewBox="0 0 24 24">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5S10.62 6.5 12 6.5s2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"></path>
              </svg>
              Ver ubicación
            </button>
          </div>
        </article>
      </div>
    `;
  }
}

customElements.define('property-card-v2', PropertyCard);
