
import { GridBase } from './GridBase.js';
import { resolveActionUrl } from './actionContract.js';

export class LeadsGrid extends GridBase {
    constructor(container, config) {
        super(container, config);
        this.init(); // Start the lifecycle defined in GridBase
    }

    renderSkeleton() {
        // Initial Loading State & Structure
        this.container.innerHTML = `
            <div class="custom-grid-wrapper">
                <div class="custom-grid-header mb-2 d-flex justify-content-between">
                    <div class="grid-controls"></div>
                    <div id="${this.container.id}-loader" class="text-muted small">Loading...</div>
                </div>
                <div class="table-responsive">
                    <table class="table table-hover table-nowrap align-middle">
                        <thead>
                            <tr>${this.config.columns.map(c => `<th>${c.label || c.name}</th>`).join('')}<th></th></tr>
                        </thead>
                        <tbody>
                            <tr><td colspan="${this.config.columns.length + 1}" class="text-center p-4">
                                <div class="spinner-border text-primary spinner-sm"></div>
                            </td></tr>
                        </tbody>
                    </table>
                </div>
                <div class="custom-grid-footer mt-2 d-flex justify-content-between align-items-center">
                    <span id="${this.container.id}-info" class="text-muted small"></span>
                    <ul id="${this.container.id}-pager" class="pagination pagination-sm mb-0"></ul>
                </div>
            </div>
            <style>
                .custom-grid-wrapper th {
                    cursor: pointer;
                    user-select: none;
                    transition: all 0.2s ease;
                    background-color: var(--vz-light);
                    color: var(--vz-body-color);
                    font-size: 13px;
                    font-weight: 600;
                    letter-spacing: 0.01em;
                    text-transform: none;
                    white-space: nowrap;
                    vertical-align: middle;
                }
                .custom-grid-wrapper th:hover { background-color: var(--vz-secondary-bg-subtle) !important; color: var(--vz-secondary) !important; }
                .badge-pill-custom { padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 11px; display: inline-block; min-width: 80px; text-align: center; background: transparent !important; }
                .sort-icon { margin-left: 5px; opacity: 0.5; font-size: 20px; font-weight: bold; }
                .active-sort { opacity: 1; color: var(--vz-primary); font-size: 20px; font-weight: bold; }
                .custom-grid-wrapper th.sorted-column { background-color: var(--vz-secondary-bg-subtle) !important; }
                .grid-head-icon {
                    font-size: 1.15em;
                    line-height: inherit;
                    opacity: 0.7;
                    vertical-align: -1px;
                }
                .grid-head-sort {
                    margin-left: 6px;
                    font-size: 13px;
                    opacity: 0.85;
                    display: inline-block;
                    line-height: 1;
                }
                .lead-identity-wrap { min-width: 0; }
                .lead-score-btn {
                    min-width: 40px;
                    height: 28px;
                    padding: 0 10px;
                    flex-shrink: 0;
                    border-radius: 8px;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;
                    font-weight: 700;
                    line-height: 1;
                    font-variant-numeric: tabular-nums;
                }
            </style>
        `;
    }

    _isCssColor(value) {
        if (typeof value !== 'string') return false;
        const c = value.trim();
        return (
            c.startsWith('#') ||
            c.startsWith('rgb(') ||
            c.startsWith('rgba(') ||
            c.startsWith('hsl(') ||
            c.startsWith('hsla(') ||
            c.startsWith('var(')
        );
    }

    _resolveIdentityColor(rawColor, score) {
        if (this._isCssColor(rawColor)) return rawColor;

        const token = String(rawColor || '').trim().toLowerCase();
        const thermalPalette = {
            'thermal-extreme': '#f06548',
            'thermal-high': '#f7b84b',
            'thermal-mid': '#4b38b3',
            'thermal-low': '#0ab39c',
            'thermal-none': 'var(--vz-secondary-color)',
            'thermal-info': '#299cdb'
        };
        if (thermalPalette[token]) return thermalPalette[token];

        const bootstrapToken = new Set([
            'primary', 'secondary', 'success', 'info', 'warning', 'danger', 'light', 'dark'
        ]);
        if (bootstrapToken.has(token)) return `var(--vz-${token})`;

        if (score >= 8) return '#0AB39C';
        if (score >= 4) return '#F7B84B';
        return '#4F7CF3';
    }

    _formatScore(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return '0';
        const clamped = Math.max(0, Math.min(10, numeric));
        if (Math.abs(clamped - Math.round(clamped)) < 0.05) return String(Math.round(clamped));
        return clamped.toFixed(1);
    }

    _formatHeaderLabel(value) {
        const text = String(value || '').replace(/\s+/g, ' ').trim();
        if (!text) return '';
        const hasUpperLetters = /[A-ZÀ-Þ]/.test(text);
        const hasLowerLetters = /[a-zà-ÿ]/.test(text);

        // Normalize "ALL CAPS" labels into sentence case.
        if (hasUpperLetters && !hasLowerLetters && text === text.toUpperCase()) {
            const lowered = text.toLowerCase();
            return lowered.charAt(0).toUpperCase() + lowered.slice(1);
        }

        // Also normalize fully lowercase labels from dynamic DB columns.
        if (!hasUpperLetters && hasLowerLetters && text === text.toLowerCase()) {
            return text.charAt(0).toUpperCase() + text.slice(1);
        }
        return text;
    }

    // Override: Define how to retrieve values for sorting specific columns
    getSortValue(row, col) {
        if (col.type === 'scoring-pillar') {
            const item = row[col.id];
            // Sort by Score (numeric) or Label (string)
            if (item && typeof item === 'object') {
                return item.score ?? item.value ?? item.label ?? 0;
            }
            return 0;
        }
        if (col.id === 'identity') {
            return Number(row.score_total || row.identity?.score || 0);
        }
        return super.getSortValue(row, col);
    }

    render() {
        const rows = this.getPaginatedRows(); // Provided by GridBase
        const pageIcons = { asc: '↑', desc: '↓' };
        const renderHeaderIcon = (icon) => {
            if (!icon) return '';
            if (typeof icon === 'string' && icon.startsWith('ri-')) {
                return `<i class="${icon} grid-head-icon me-1 text-muted"></i>`;
            }
            return `<span class="me-1 text-muted">${icon}</span>`;
        };

        // Render Header
        const thead = this.config.columns.map(c => {
            const isSorted = this.sortState.colId === c.id;
            const icon = renderHeaderIcon(c.icon);
            const label = this._formatHeaderLabel(c.label || c.name);
            return `<th onclick="window.gridInstances['${this.container.id}'].handleSort('${c.id}')">
                ${icon}${label}${isSorted ? `<span class="grid-head-sort">${pageIcons[this.sortState.direction]}</span>` : ''}
            </th>`;
        }).join('') + '<th></th>';

        // Render Body
        const tbody = rows.map(row => `
            <tr onclick="window.gridInstances['${this.container.id}'].handleRowNavigate('${row.id}', event)" style="cursor: pointer;">
                ${this.config.columns.map(col => `<td>${this.renderCell(row, col)}</td>`).join('')}
                <td onclick="event.stopPropagation()">${this.renderActions(row)}</td>
            </tr>
        `).join('');

        const table = this.container.querySelector('table');
        if (table) {
            table.querySelector('thead tr').innerHTML = thead;
            table.querySelector('tbody').innerHTML = tbody || '<tr><td colspan="100" class="text-center text-muted">No data found</td></tr>';
        }

        this.renderPager();
    }

    renderCell(row, col) {
        // Identity Column
        if (col.id === 'identity' || col.type === 'gauge-identity') {
            const identity = row.identity || {};
            const score = Number(identity.score ?? row.score_total ?? 0);
            const name = identity.name || row.full_name || 'Unknown';
            const email = row.email || '-';
            const displayScore = this._formatScore(score);
            const normalized = Math.max(0, Math.min(10, Number.isFinite(score) ? score : 0));
            const toneColor = this._resolveIdentityColor(identity.color, normalized);
            const scoreButtonStyle = [
                `color:${toneColor}`,
                `border:1px solid ${toneColor}`,
                'background-color: transparent',
                `background: color-mix(in srgb, ${toneColor}, transparent 88%)`
            ].join(';');

            return `
                <div class="d-flex align-items-center lead-identity-wrap">
                    <span class="lead-score-btn me-2" style="${scoreButtonStyle}" title="Score: ${displayScore}/10">${displayScore}</span>
                    <div style="min-width:0;">
                        <div class="fw-bold" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:150px;">
                            <a href="#" onclick="event.preventDefault(); window.gridInstances['${this.container.id}'].handleRowNavigate('${row.id}', event)" class="text-reset text-decoration-none">${name}</a>
                        </div>
                        <div class="text-muted" style="font-size:10px;">${email}</div>
                    </div>
                </div>
            `;
        }

        // Scoring Pillars
        if (col.type === 'scoring-pillar') {
            const item = row[col.id] || {};
            const label = item.label || null;
            const rawColor = item.color || 'secondary';
            const isCssColor = typeof rawColor === 'string' && (
                rawColor.startsWith('#') ||
                rawColor.startsWith('rgb(') ||
                rawColor.startsWith('rgba(') ||
                rawColor.startsWith('hsl(') ||
                rawColor.startsWith('hsla(') ||
                rawColor.startsWith('var(')
            );
            const icon = item.icon || '';
            const iconHtml = icon
                ? (
                    icon.startsWith('ri-')
                        ? `<i class="${icon} me-2 align-middle fs-22 ${isCssColor ? '' : `text-${rawColor}`}" ${isCssColor ? `style="color:${rawColor};"` : ''}></i>`
                        : `<span class="me-2 align-middle">${icon}</span>`
                )
                : '';

            // Special handling for preference/status
            if (col.id === 'contact_preference' || col.id === 'status') {
                if (!label) return `<span class="text-muted fst-italic">-</span>`;
                return `<span class="d-inline-flex align-items-center">${iconHtml}<span class="text-body fw-normal">${label}</span></span>`;
            }

            // Default Pill Style
            const displayLabel = label || '-';
            if (isCssColor) {
                return `<span class="badge-pill-custom border" style="color:${rawColor}; border-color:${rawColor} !important;">${displayLabel.toUpperCase()}</span>`;
            }
            return `<span class="badge-pill-custom text-${rawColor} border border-${rawColor}">${displayLabel.toUpperCase()}</span>`;
        }

        return row[col.id] || '-';
    }

    renderActions(row) {
        const actions = Array.isArray(this.config.actions) ? this.config.actions : [];
        const rendered = actions
            .filter((action) => action?.action === 'navigate')
            .map((action, idx) => {
                const icon = action.icon || 'ri-arrow-right-line';
                const label = action.label || 'Abrir';
                return `
                    <button class="btn btn-sm btn-soft-secondary me-1"
                        title="${label}"
                        onclick="window.gridInstances['${this.container.id}'].executeAction('${row.id}', ${idx}, event)">
                        <i class="${icon}"></i>
                    </button>
                `;
            })
            .join('');

        if (rendered) return rendered;
        return `
            <button class="btn btn-sm btn-soft-secondary"
                onclick="window.gridInstances['${this.container.id}'].handleRowNavigate('${row.id}', event)">
                <i class="ri-eye-line"></i>
            </button>
        `;
    }

    handleRowNavigate(rowId, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        const row = this.data.find((item) => String(item?.id ?? '') === String(rowId));
        if (!row) return;

        const navigateAction = (this.config.actions || []).find((action) => action?.action === 'navigate');
        const targetUrl = navigateAction
            ? resolveActionUrl(navigateAction, row)
            : `/dashboard/leads/${row.id}`;

        if (targetUrl && window.navigateTo) {
            window.navigateTo(targetUrl);
        }
    }

    executeAction(rowId, actionIndex, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        const row = this.data.find((item) => String(item?.id ?? '') === String(rowId));
        if (!row) return;
        const actions = Array.isArray(this.config.actions) ? this.config.actions : [];
        const navigateActions = actions.filter((action) => action?.action === 'navigate');
        const selected = navigateActions[actionIndex];
        if (!selected) return;

        const targetUrl = resolveActionUrl(selected, row);
        if (targetUrl && window.navigateTo) {
            window.navigateTo(targetUrl);
        }
    }

    renderPager() {
        const total = this.filteredData.length; // From Base
        const totalPages = Math.ceil(total / this.pageSize);
        const start = (this.currentPage - 1) * this.pageSize + 1;
        const end = Math.min(start + this.pageSize - 1, total);

        const infoEl = this.container.querySelector(`#${this.container.id}-info`);
        if (infoEl) infoEl.innerText = `Showing ${start}-${end} of ${total}`;

        // Simple Pager
        let html = '';
        if (totalPages > 1) {
            html += `<li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}"><a class="page-link" href="#" onclick="window.gridInstances['${this.container.id}'].setPage(${this.currentPage - 1}); return false;">Prev</a></li>`;
            html += `<li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}"><a class="page-link" href="#" onclick="window.gridInstances['${this.container.id}'].setPage(${this.currentPage + 1}); return false;">Next</a></li>`;
        }
        const pagerEl = this.container.querySelector(`#${this.container.id}-pager`);
        if (pagerEl) pagerEl.innerHTML = html;
    }
}
