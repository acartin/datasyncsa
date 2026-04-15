import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

class PropertyCard extends LitElement {
  static properties = {
    title: { type: String },
    price: { type: Number },
    location: { type: String },
    imageUrl: { type: String },
    publicUrl: { type: String },
    bedrooms: { type: Number },
    bathrooms: { type: Number },
    sqm: { type: Number },
    garage: { type: Number },
    amenities: { type: Array },
    description: { type: String }
  };

  static styles = css`
    :host { display: block; margin-bottom: 1rem; }
    .card {
      background: rgba(255,255,255,0.05);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 16px;
      overflow: hidden;
      color: white;
      transition: all 0.3s ease;
    }
    .card.expanded {
      border-color: rgba(99,102,241,0.5);
      box-shadow: 0 8px 32px rgba(99,102,241,0.2);
    }
    img { width: 100%; height: 180px; object-fit: cover; }
    .content { padding: 1rem; }
    h3 { margin: 0; font-size: 1.1rem; font-weight: 700; }
    .price { color: #6366f1; font-size: 1.25rem; font-weight: 700; margin: 0.5rem 0; }
    .location { font-size: 0.85rem; opacity: 0.7; margin-bottom: 1rem; }
    .badge { background: #4b38b3; font-size: 0.7rem; padding: 4px 8px; border-radius: 6px; }
    .btn { width: 100%; background: linear-gradient(135deg, #6366f1, #8b5cf6); border: none; color: white; padding: 12px; border-radius: 8px; font-weight: 700; cursor: pointer; }
    .quick { display: flex; gap: 1rem; margin: 0.75rem 0; padding: 0.75rem 0; border-top: 1px solid rgba(255,255,255,0.1); }
    .quick span { font-size: 0.85rem; opacity: 0.8; }
    .details { max-height: 0; overflow: hidden; transition: max-height 0.4s; }
    .card.expanded .details { max-height: 500px; padding-top: 1rem; }
    .amenities { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 0.5rem; }
    .tag { background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.3); color: #a5b4fc; font-size: 0.75rem; padding: 4px 10px; border-radius: 20px; }
    .desc { font-size: 0.85rem; line-height: 1.5; opacity: 0.8; margin-top: 0.5rem; }
  `;

  constructor() { super(); this._expanded = false; }

  _toggle() { this._expanded = !this._expanded; this.requestUpdate(); }

  render() {
    const pf = new Intl.NumberFormat('es-CR', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(this.price || 0);
    return html`
      <div class="card ${this._expanded ? 'expanded' : ''}">
        ${this.imageUrl ? html`<img src="${this.imageUrl}">` : ''}
        <div class="content">
          <span class="badge">Propiedad</span>
          <h3>${this.title}</h3>
          <div class="price">${pf}</div>
          <div class="location">📍 ${this.location}</div>
          <div class="quick">
            ${this.bedrooms ? html`<span>🛏️ ${this.bedrooms}</span>` : ''}
            ${this.bathrooms ? html`<span>🚿 ${this.bathrooms}</span>` : ''}
            ${this.sqm ? html`<span>📐 ${this.sqm}m²</span>` : ''}
          </div>
          <div class="details">
            ${this.description ? html`<p class="desc">${this.description}</p>` : ''}
            ${this.amenities?.length ? html`
              <div class="amenities">
                ${this.amenities.slice(0,6).map(a => html`<span class="tag">${a}</span>`)}
              </div>
            ` : ''}
          </div>
          <button class="btn" @click="${this._toggle}">
            ${this._expanded ? '✕ Cerrar' : '👁️ Ver detalles'}
          </button>
        </div>
      </div>
    `;
  }
}

customElements.define('property-card-v2', PropertyCard);