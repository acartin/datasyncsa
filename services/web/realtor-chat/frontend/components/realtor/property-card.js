import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

class PropertyCard extends LitElement {
  static properties = {
    title: { type: String },
    price: { type: Number },
    location: { type: String },
    imageUrl: { type: String }
  };

  static styles = css`
    :host {
      display: block;
      margin-bottom: 1rem;
    }
    .card {
      background: var(--brand-surface, rgba(255, 255, 255, 0.05));
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: var(--border-radius, 16px);
      overflow: hidden;
      color: var(--text-on-surface, white);
      box-shadow: var(--box-shadow, 0 4px 12px rgba(0,0,0,0.1));
      transition: transform 0.3s ease;
      font-family: var(--font-body, sans-serif);
    }
    .card:hover {
      transform: translateY(-5px);
      border-color: rgba(255, 255, 255, 0.3);
    }
    img {
      width: 100%;
      height: 180px;
      object-fit: cover;
    }
    .content {
      padding: 1rem;
    }
    h3 {
      margin: 0;
      font-family: var(--font-heading, sans-serif);
      font-size: 1.1rem;
      font-weight: 700;
    }
    .price {
      color: var(--text-on-surface, #6366f1);
      font-size: 1.25rem;
      font-weight: 700;
      margin: 0.5rem 0;
    }
    .location {
      font-size: 0.85rem;
      opacity: 0.7;
      display: flex;
      align-items: center;
      gap: 4px;
      margin-bottom: 1rem;
    }
    .badge {
      background: var(--brand-primary, #4b38b3);
      color: var(--text-on-primary, white);
      font-size: 0.7rem;
      padding: 4px 8px;
      border-radius: 6px;
      text-transform: uppercase;
    }
    .btn-action {
      width: 100%;
      background: var(--brand-secondary, rgba(99, 102, 241, 0.2));
      border: none;
      color: var(--text-on-secondary, white);
      padding: 12px;
      border-radius: calc(var(--border-radius, 16px) / 2);
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s ease;
      font-size: 0.9rem;
      text-align: center;
    }
    .btn-action:hover {
      filter: brightness(1.2);
    }
  `;

  _handleMapClick() {
    this.dispatchEvent(new CustomEvent('property-open-map', {
      detail: {
        title: this.title,
        location: this.location
      },
      bubbles: true,
      composed: true
    }));
  }

  render() {
    return html`
      <div class="card">
        ${this.imageUrl ? html`<img src="${this.imageUrl}" alt="${this.title}">` : ''}
        <div class="content">
          <span class="badge">Propiedad Destacada</span>
          <h3>${this.title || 'Propiedad sin título'}</h3>
          <div class="price">
            ${new Intl.NumberFormat('es-CR', { style: 'currency', currency: 'USD' }).format(this.price || 0)}
          </div>
          <div class="location">
             📍 ${this.location || 'Ubicación no disponible'}
          </div>
          <button class="btn-action" @click="${this._handleMapClick}">
            📍 Abrir Mapa
          </button>
        </div>
      </div>
    `;
  }
}

customElements.define('property-card', PropertyCard);
