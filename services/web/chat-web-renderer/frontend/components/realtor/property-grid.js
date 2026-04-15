import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class PropertyGrid extends LitElement {
    static properties = {
        title: { type: String },
        properties: { type: Array }
    };

    static styles = css`
        :host {
            display: block;
            width: 100%;
            color: var(--text-on-surface, #f8fafc);
            font-family: var(--font-body, sans-serif);
        }

        .grid-shell {
            display: grid;
            gap: 0.85rem;
        }

        .grid-title {
            color: rgba(248, 250, 252, 0.82);
            font-family: var(--font-heading, sans-serif);
            font-size: 0.92rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }

        .grid-container {
            display: grid;
            grid-auto-flow: column;
            grid-auto-columns: minmax(284px, 72%);
            gap: 0.9rem;
            overflow-x: auto;
            padding: 0.15rem 0.1rem 0.45rem;
            scroll-snap-type: x proximity;
            scrollbar-width: thin;
            scrollbar-color: rgba(255, 255, 255, 0.14) transparent;
        }

        .grid-container::-webkit-scrollbar {
            height: 6px;
        }

        .grid-container::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.14);
            border-radius: 999px;
        }

        .grid-item {
            min-width: 0;
            scroll-snap-align: start;
        }

        @media (max-width: 640px) {
            .grid-container {
                grid-auto-columns: minmax(248px, 88%);
            }
        }

        @media (min-width: 900px) {
            .grid-container {
                grid-auto-columns: minmax(300px, 360px);
            }
        }
    `;

    render() {
        return html`
            <div class="grid-shell">
                ${this.title ? html`<div class="grid-title">${this.title}</div>` : ''}
                <div class="grid-container">
                    ${this.properties?.map((p) => {
                        const features = p.features || {};
                        return html`
                            <div class="grid-item">
                                <property-card-v2
                                    .title=${p.title}
                                    .price=${p.price}
                                    .currency=${p.currency}
                                    .priceNote=${p.price_note}
                                    .location=${p.location}
                                    .imageUrl=${p.image_url}
                                    .imageUrls=${p.image_urls || []}
                                    .photoCount=${p.photo_count}
                                    .publicUrl=${p.public_url}
                                    .features=${features}
                                    .tags=${p.tags || []}
                                    .badgeMain=${p.badge_main}
                                    .badgeSub=${p.badge_sub}
                                    .bedrooms=${p.bedrooms_clean ?? features.bedrooms_clean ?? features.bedrooms}
                                    .bathrooms=${p.bathrooms_clean ?? features.bathrooms_clean ?? features.bathrooms}
                                    .sqm=${p.sqm_clean ?? features.sqm_clean ?? features.sqm ?? features.area_display}
                                    .garage=${p.garage_clean ?? features.garage_clean ?? features.garage}
                                    .amenities=${p.amenities || features.amenities || []}
                                    .description=${p.description || features.description || ''}>
                                </property-card-v2>
                            </div>
                        `;
                    })}
                </div>
            </div>
        `;
    }
}

customElements.define('property-grid', PropertyGrid);
