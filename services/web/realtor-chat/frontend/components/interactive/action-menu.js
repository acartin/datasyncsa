import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class ActionMenu extends LitElement {
    static properties = {
        title: { type: String },
        options: { type: Array }
    };

    static styles = css`
        :host {
            display: block;
            margin-top: 10px;
        }
        .menu-container {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        button {
            background: var(--brand-secondary, rgba(255, 255, 255, 0.1));
            border: none;
            color: var(--text-on-secondary, white);
            padding: 8px 20px;
            border-radius: var(--border-radius, 20px);
            cursor: pointer;
            font-family: var(--font-body, sans-serif);
            font-weight: 700;
            transition: all 0.3s ease;
        }
        button:hover {
            filter: brightness(1.2);
            transform: translateY(-2px);
        }
    `;

    render() {
        return html`
            <div class="menu-container">
                ${this.options?.map(opt => html`
                    <button @click="${() => this._handleAction(opt.payload)}">
                        ${opt.label}
                    </button>
                `)}
            </div>
        `;
    }

    _handleAction(payload) {
        this.dispatchEvent(new CustomEvent('chat-action', {
            detail: { payload },
            bubbles: true,
            composed: true
        }));
    }
}

customElements.define('action-menu', ActionMenu);
