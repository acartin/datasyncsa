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
            overflow-x: auto;
            padding-bottom: 10px;
        }
        .grid-container {
            display: flex;
            gap: 15px;
            padding: 5px;
        }
        ::slotted(property-card) {
            flex: 0 0 250px;
        }
    `;

    render() {
        return html`
            <div class="grid-container">
                ${this.properties?.map(p => html`
                    <property-card 
                        .title="${p.title}" 
                        .price="${p.price}" 
                        .location="${p.location}" 
                        .imageUrl="${p.image_url}"
                        .publicUrl="${p.public_url}">
                    </property-card>
                `)}
            </div>
        `;
    }
}

customElements.define('property-grid', PropertyGrid);
