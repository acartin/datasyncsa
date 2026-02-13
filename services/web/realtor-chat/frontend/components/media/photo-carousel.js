import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class PhotoCarousel extends LitElement {
    static properties = {
        images: { type: Array },
        showThumbnails: { type: Boolean, attribute: 'show-thumbnails' },
        currentIndex: { type: Number },
    };

    constructor() {
        super();
        this.images = [];
        this.showThumbnails = false;
        this.currentIndex = 0;
    }

    static styles = css`
        :host {
            display: block;
            width: 100%;
            height: 220px;
            background: #334155;
            border-radius: 12px;
            overflow: hidden;
            position: relative;
            color: white;
        }
        img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .empty {
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .controls {
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            display: flex;
            justify-content: space-between;
            transform: translateY(-50%);
            padding: 0 8px;
        }
        button {
            border: none;
            background: rgba(0, 0, 0, 0.4);
            color: white;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
        }
    `;

    _next() {
        if (!this.images?.length) return;
        this.currentIndex = (this.currentIndex + 1) % this.images.length;
    }

    _prev() {
        if (!this.images?.length) return;
        this.currentIndex = (this.currentIndex - 1 + this.images.length) % this.images.length;
    }

    render() {
        const hasImages = Array.isArray(this.images) && this.images.length > 0;
        const image = hasImages ? this.images[this.currentIndex] : null;

        return html`
            <div class="${hasImages ? '' : 'empty'}">
                ${hasImages
                    ? html`
                        <img src="${image}" alt="Foto de propiedad" loading="lazy" />
                        ${this.images.length > 1
                            ? html`
                                <div class="controls">
                                    <button @click="${this._prev}" aria-label="Anterior">‹</button>
                                    <button @click="${this._next}" aria-label="Siguiente">›</button>
                                </div>
                            `
                            : ''}
                    `
                    : html`<p>Carrusel de Fotos (0 imágenes)</p>`
                }
            </div>
        `;
    }
}

customElements.define('photo-carousel', PhotoCarousel);
