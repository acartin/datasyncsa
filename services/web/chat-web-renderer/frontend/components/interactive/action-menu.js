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
        .menu-title {
            margin-bottom: 8px;
            color: var(--text-on-surface, white);
            font-family: var(--font-body, sans-serif);
            font-size: 13px;
            font-weight: 600;
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
            ${this.title ? html`<div class="menu-title">${this.title}</div>` : ''}
            <div class="menu-container">
                ${this.options?.map(opt => html`
                    <button @click="${() => this._handleAction(opt)}">
                        ${opt.label}
                    </button>
                `)}
            </div>
        `;
    }

    _handleAction(option) {
        if (option && typeof option === 'object' && (option.action_id || option.user_text)) {
            this.dispatchEvent(new CustomEvent('chat-action', {
                detail: {
                    payload: {
                        type: 'action_menu_option',
                        actionId: option.action_id || option.payload || null,
                        actionLabel: option.label || null,
                        userText: option.user_text || option.label || '',
                    }
                },
                bubbles: true,
                composed: true
            }));
            return;
        }

        this.dispatchEvent(new CustomEvent('chat-action', {
            detail: { payload: option?.payload ?? option },
            bubbles: true,
            composed: true
        }));
    }
}

customElements.define('action-menu', ActionMenu);
