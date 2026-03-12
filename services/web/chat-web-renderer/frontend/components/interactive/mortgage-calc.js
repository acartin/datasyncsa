import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

export class MortgageCalculator extends LitElement {
    static properties = {
        propertyPrice: { type: Number, attribute: 'property-price' },
        defaultInterest: { type: Number, attribute: 'default-interest' },
        termYears: { type: Number },
        downPaymentPercent: { type: Number },
    };

    constructor() {
        super();
        this.propertyPrice = 0;
        this.defaultInterest = 8.5;
        this.termYears = 30;
        this.downPaymentPercent = 20;
    }

    static styles = css`
        :host {
            display: block;
            background: var(--brand-surface, rgba(255, 255, 255, 0.05));
            border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.1));
            border-radius: var(--border-radius, 12px);
            padding: 15px;
            color: var(--text-on-surface, white);
            box-shadow: var(--box-shadow, none);
            font-family: var(--font-body, sans-serif);
        }
        .title { 
            font-weight: 700;
            font-family: var(--font-heading, sans-serif);
            margin-bottom: 10px; 
            display: block;
            color: var(--brand-secondary, #6366f1);
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }
        label {
            font-size: 0.8rem;
            opacity: 0.9;
            display: block;
        }
        input {
            width: 100%;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.1));
            border-radius: 8px;
            color: inherit;
            padding: 8px;
            margin-top: 4px;
        }
        .result {
            margin-top: 12px;
            font-weight: 700;
            color: var(--text-on-surface, white);
        }
    `;

    _calculateMonthlyPayment() {
        const principal = Math.max(0, (this.propertyPrice || 0) * (1 - (this.downPaymentPercent || 0) / 100));
        const monthlyRate = ((this.defaultInterest || 0) / 100) / 12;
        const months = Math.max(1, (this.termYears || 1) * 12);
        if (!principal) return 0;
        if (!monthlyRate) return principal / months;
        const factor = Math.pow(1 + monthlyRate, months);
        return (principal * monthlyRate * factor) / (factor - 1);
    }

    render() {
        const monthly = this._calculateMonthlyPayment();
        return html`
            <div class="calc-container">
                <span class="title">Calculadora para: $${(this.propertyPrice || 0).toLocaleString()}</span>
                <div class="grid">
                    <div>
                        <label>Tasa anual (%)</label>
                        <input
                            type="number"
                            step="0.1"
                            .value="${String(this.defaultInterest || 0)}"
                            @input="${(e) => { this.defaultInterest = Number(e.target.value); }}"
                        />
                    </div>
                    <div>
                        <label>Plazo (años)</label>
                        <input
                            type="number"
                            step="1"
                            min="1"
                            .value="${String(this.termYears || 30)}"
                            @input="${(e) => { this.termYears = Number(e.target.value); }}"
                        />
                    </div>
                    <div>
                        <label>Prima (%)</label>
                        <input
                            type="number"
                            step="1"
                            min="0"
                            max="95"
                            .value="${String(this.downPaymentPercent || 20)}"
                            @input="${(e) => { this.downPaymentPercent = Number(e.target.value); }}"
                        />
                    </div>
                </div>
                <div class="result">
                    Cuota estimada: ${new Intl.NumberFormat('es-CR', { style: 'currency', currency: 'USD' }).format(monthly)}
                </div>
            </div>
        `;
    }
}

customElements.define('mortgage-calculator', MortgageCalculator);
