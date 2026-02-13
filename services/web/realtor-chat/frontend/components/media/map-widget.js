import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class PropertyMap extends LitElement {
    static properties = {
        center: { type: Object },
        zoom: { type: Number },
        pois: { type: Array }
    };

    static styles = css`
        :host {
            display: block;
            height: 200px;
            background: #1e293b;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #94a3b8;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
    `;

    render() {
        const lat = this.center?.lat;
        const lng = this.center?.lng;
        const hasCoords = typeof lat === 'number' && typeof lng === 'number';
        const mapUrl = hasCoords
            ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${lat},${lng}`)}`
            : 'https://www.google.com/maps';

        return html`
            <div>
                <p>${hasCoords ? 'Ubicación sugerida' : 'Mapa de la zona'}</p>
                <small>Lat: ${lat ?? '-'}, Lng: ${lng ?? '-'}</small>
                <div style="margin-top:8px;">
                    <a href="${mapUrl}" target="_blank" rel="noopener noreferrer">Abrir en Google Maps</a>
                </div>
            </div>
        `;
    }
}

customElements.define('property-map', PropertyMap);
