
import { GridBase } from './GridBase.js';
import { formatters } from './formatters.js';
import { resolveActionUrl, resolveSchemaB64 } from './actionContract.js';
import { ensureDynamicClass } from './themeTokens.js';

/**
 * TableGrid - Generic Grid Implementation
 * Replaces Grid.js StandardGrid with a native implementation extending GridBase.
 * Handles:
 * - Generic Column Rendering
 * - Custom Formatters (Badge, Truncate)
 * - Action Dropdowns
 */
export class TableGrid extends GridBase {
    constructor(container, config) {
        super(container, config);
        // console.log(`[TableGrid] Initializing for container: ${container.id}`);

        // Ensure actions are parsed
        this.actions = this.config.actions || [];
        this.headerActions = this.config.header_actions || [];
        this.schemaStr = container.dataset.schema || '[]'; // Global/Edit schema

        this.init();
    }

    renderSkeleton() {
        this.container.innerHTML = `
            <div class="table-grid-wrapper table-grid-shell">
                <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3 grid-header-controls">
                    <!-- Filters will inject here -->
                    <div class="grid-header-actions d-flex gap-2"></div>
                    <div id="${this.container.id}-loader" class="text-muted small ms-auto table-grid-loader">Loading...</div>
                </div>
                <div class="table-responsive table-grid-responsive">
                    <table class="table table-hover align-middle mb-0 table-grid-table">
                        <thead class="table-light text-muted">
                            <tr>${this.config.columns.map(c => `
                                <th class="sortable text-uppercase table-grid-head" onclick="window.gridInstances['${this.container.id}'].handleSort('${c.id}')">
                                    ${this.getColumnHeaderLabel(c)}
                                </th>`).join('')}
                                ${this.actions.length > 0 ? '<th></th>' : ''}
                            </tr>
                        </thead>
                        <tbody>
                             <tr><td colspan="100" class="text-center p-5"><div class="spinner-border text-primary spinner-sm"></div></td></tr>
                        </tbody>
                    </table>
                </div>
                 <div class="d-flex justify-content-between align-items-center mt-3 grid-footer">
                    <span id="${this.container.id}-info" class="text-muted small"></span>
                    <ul id="${this.container.id}-pager" class="pagination pagination-sm mb-0"></ul>
                </div>
            </div>
        `;
    }

    // Called by GridBase.init()
    render() {
        // Only render header actions here if Filters are disabled (otherwise GridFilters handles it)
        if (!this.config.enableFilters) {
            this.renderHeaderActions();
        }

        const rows = this.getPaginatedRows();
        // console.log(`[TableGrid] Rendering ${rows.length} rows. Columns:`, this.config.columns);
        // ... (resto del render) ...
        const pageIcons = { asc: '↑', desc: '↓' };

        // ... (renderizado de tabla) ...
        // Re-use existing render logic but ensure renderHeaderActions calls only once ideally, or idempotent.

        // 1. Render Header (Update sort icons)
        const theadHtml = `
            <tr>
                ${this.config.columns.map(c => {
            const isSorted = this.sortState.colId === c.id;
            const sortIcon = isSorted ? `<span class="ms-1 text-primary">${pageIcons[this.sortState.direction]}</span>` : '';
            return `
                        <th class="sortable cursor-pointer" onclick="window.gridInstances['${this.container.id}'].handleSort('${c.id}')">
                            ${this.getColumnHeaderLabel(c)} ${sortIcon}
                        </th>`;
        }).join('')}
                ${this.actions.length > 0 ? '<th class="table-grid-actions-col"></th>' : ''}
            </tr>
        `;

        // 2. Render Body
        const tbodyHtml = rows.map(row => {
            const rowId = row.id ?? '';
            const isSelected = String(this.selectedRowId ?? '') === String(rowId);
            const selectedClass = isSelected ? 'grid-row-selected' : '';
            return `
            <tr class="${selectedClass} table-grid-row-clickable" onclick="window.gridInstances['${this.container.id}'].handleRowClick('${rowId}', event)" ondblclick="window.gridInstances['${this.container.id}'].handleRowDoubleClick('${rowId}', event)">
                ${this.config.columns.map(col => `<td>${this.renderCell(row, col)}</td>`).join('')}
                ${this.actions.length > 0 ? `<td>${this.renderActions(row)}</td>` : ''}
            </tr>
        `;
        }).join('');

        // Apply to DOM
        const table = this.container.querySelector('table');
        if (table) {
            table.querySelector('thead').innerHTML = theadHtml;
            table.querySelector('tbody').innerHTML = tbodyHtml || '<tr><td colspan="100" class="text-center text-muted p-4">No data found</td></tr>';
        }

        this.renderPager();
    }

    renderHeaderActions() {
        const container = this.container.querySelector('.grid-header-actions');
        if (!container || !this.headerActions.length) return;

        // Clean to avoid duplicates on re-render
        container.innerHTML = '';

        const resolveTokens = (value, rowLike = {}) => {
            if (typeof value !== 'string') return value;
            let resolved = value;
            Object.entries(rowLike || {}).forEach(([rk, rv]) => {
                resolved = resolved.replace(new RegExp(`\\{${rk}\\}`, 'g'), String(rv ?? ''));
            });
            return resolved;
        };

        const encodeB64 = (obj) => btoa(unescape(encodeURIComponent(JSON.stringify(obj || {}))));

        const contextTokens = {
            ...(this.config.context || {}),
            ...(this.masterValue ? { master_id: this.masterValue } : {}),
        };

        const buttons = this.headerActions.map(act => {
            if (act.requires_master && !contextTokens.master_id) {
                if (act.show_disabled_when_locked) {
                    const lockedColor = act.color || 'secondary';
                    const lockedIcon = act.icon || 'ri-lock-line';
                    const lockedLabel = act.locked_label || act.label || 'Bloqueado';
                    return `
                        <button class="btn btn-${lockedColor} btn-sm waves-effect waves-light" disabled>
                            <i class="${lockedIcon} me-1 align-bottom"></i> ${lockedLabel}
                        </button>
                    `;
                }
                return '';
            }
            const schemaToPass = resolveSchemaB64(act, {
                formSchema: this.config.form_schema,
                fallbackSchema: this.schemaStr
            });

            const url = resolveActionUrl(act, contextTokens);
            const modalTitle = resolveTokens(act.modal_title || act.label, contextTokens);
            const color = act.color || 'primary';
            const icon = act.icon || 'ri-add-line';

            if (act.action === 'modal-form-create') {
                const prefill = {};
                Object.entries(act.prefill || {}).forEach(([key, value]) => {
                    prefill[key] = resolveTokens(value, contextTokens);
                });
                const prefillB64 = encodeB64(prefill);
                return `
                    <button class="btn btn-${color} btn-sm waves-effect waves-light" 
                        onclick="window.handleCreateAction(event, '${url}', '${schemaToPass}', '${modalTitle}', '${prefillB64}')">
                        <i class="${icon} me-1 align-bottom"></i> ${act.label}
                    </button>
                `;
            }

            return `
                <button class="btn btn-${color} btn-sm waves-effect waves-light" 
                    onclick="window.handleEditAction(event, '', '${url}', '${schemaToPass}', '${modalTitle}')">
                    <i class="${icon} me-1 align-bottom"></i> ${act.label}
                </button>
            `;
        }).join('');

        container.innerHTML = buttons;
    }

    getColumnHeaderLabel(col) {
        if (col && Object.prototype.hasOwnProperty.call(col, 'label')) {
            return col.label ?? '';
        }
        return col?.name ?? '';
    }

    renderCell(row, col) {
        let cellValue = row[col.id];

        // Handle Missing values
        if (cellValue === undefined || cellValue === null) return '-';

        // Apply Formatters
        if (col.type === 'badge' && formatters.badge) {
            return formatters.badge(cellValue, col);
        }

        // Color Swatch Renderer
        if (col.type === 'color') {
            const dynamicColorClass = ensureDynamicClass('tblswatch', `background-color:${cellValue};`);
            return `<div class="d-flex align-items-center gap-2">
                <div class="table-grid-color-swatch ${dynamicColorClass}"></div>
                <span class="text-muted small">${cellValue}</span>
            </div>`;
        }

        // Icon Renderer (expects Remix class like ri-*)
        if (col.type === 'icon') {
            if (typeof cellValue === 'string' && cellValue.startsWith('ri-')) {
                if (col.icon_only) {
                    return `<span class="d-inline-flex align-items-center"><i class="${cellValue} fs-18"></i></span>`;
                }
                return `<span class="d-inline-flex align-items-center gap-2"><i class="${cellValue} fs-18"></i><span class="text-muted small">${cellValue}</span></span>`;
            }
            return col.icon_only ? '' : `<span class="text-muted small">${cellValue}</span>`;
        }

        if (col.truncate && formatters.truncate) {
            return formatters.truncate(cellValue, col);
        }

        // Generic Obj Handling (e.g. nested objects shown as [Object] fix)
        if (typeof cellValue === 'object') {
            return cellValue.name || cellValue.label || JSON.stringify(cellValue);
        }

        return cellValue;
    }

    // Logic ported from StandardGrid.js but returning generic HTML string, not gridjs.html()
    renderActions(row) {
        const rowId = row.id; // Convention: all rows must have ID
        const resolveTokens = (value, rowLike = {}) => {
            if (typeof value !== 'string') return value;
            let resolved = value;
            Object.entries(rowLike || {}).forEach(([rk, rv]) => {
                resolved = resolved.replace(new RegExp(`\\{${rk}\\}`, 'g'), String(rv ?? ''));
            });
            return resolved;
        };
        const encodeB64 = (obj) => btoa(unescape(encodeURIComponent(JSON.stringify(obj || {}))));
        const decodeB64Json = (payload) => {
            try {
                return JSON.parse(decodeURIComponent(escape(atob(payload))));
            } catch (e) {
                try { return JSON.parse(atob(payload)); } catch (e2) { return {}; }
            }
        };
        const deepResolveTokens = (node, rowLike = {}) => {
            if (Array.isArray(node)) return node.map(v => deepResolveTokens(v, rowLike));
            if (node && typeof node === 'object') {
                const out = {};
                Object.entries(node).forEach(([k, v]) => { out[k] = deepResolveTokens(v, rowLike); });
                return out;
            }
            return resolveTokens(node, rowLike);
        };

        const dropdownItems = this.actions.map(act => {
            if (act.action === 'modal-form' || act.action === 'edit') {
                const schemaToPass = resolveSchemaB64(act, {
                    formSchema: this.config.form_schema,
                    fallbackSchema: this.schemaStr
                });
                const url = resolveActionUrl(act, row);

                return `<li><a class="dropdown-item" href="javascript:void(0)" onclick="window.handleEditAction(event, '${rowId}', '${url}', '${schemaToPass}')">
                    <i class="${act.icon} align-bottom me-2 text-muted"></i> ${act.label}
                </a></li>`;
            }
            if (act.action === 'modal-form-create') {
                const schemaToPass = resolveSchemaB64(act, {
                    formSchema: this.config.form_schema,
                    fallbackSchema: this.schemaStr
                });
                const url = resolveActionUrl(act, row);
                const modalTitle = act.modal_title || act.label || 'Nuevo registro';
                const prefill = {};
                Object.entries(act.prefill || {}).forEach(([key, value]) => {
                    if (typeof value !== 'string') {
                        prefill[key] = value;
                        return;
                    }
                    let resolved = value;
                    Object.entries(row).forEach(([rk, rv]) => {
                        resolved = resolved.replace(new RegExp(`\\{${rk}\\}`, 'g'), String(rv ?? ''));
                    });
                    prefill[key] = resolved;
                });
                const prefillB64 = btoa(unescape(encodeURIComponent(JSON.stringify(prefill))));
                return `<li><a class="dropdown-item" href="javascript:void(0)" onclick="window.handleCreateAction(event, '${url}', '${schemaToPass}', '${modalTitle}', '${prefillB64}')">
                    <i class="${act.icon} align-bottom me-2 text-muted"></i> ${act.label}
                </a></li>`;
            }
            if (act.action === 'modal-grid-crud') {
                const rawConfig = decodeB64Json(act.config_b64 || '');
                const contextRow = {
                    context_criterion_id: row.id,
                    context_criterion_key: row.criterion_key,
                    context_model_id: row.model_id ?? row.id,
                    context_model_name: row.model_name ?? row.name
                };
                const resolvedConfig = deepResolveTokens(rawConfig, contextRow);
                resolvedConfig.context = contextRow;
                const configB64 = encodeB64(resolvedConfig);
                const modalTitle = resolveTokens(act.modal_title || act.label || 'Gestión', contextRow).replace(/'/g, "\\'");
                return `<li><a class="dropdown-item" href="javascript:void(0)" onclick="window.openCrudGridModal(event, '${modalTitle}', '${configB64}')">
                    <i class="${act.icon} align-bottom me-2 text-muted"></i> ${act.label}
                </a></li>`;
            }
            if (act.action === 'navigate') {
                const url = resolveActionUrl(act, row);
                return `<li><a class="dropdown-item" href="javascript:void(0)" onclick="window.navigateTo('${url}')">
                    <i class="${act.icon} align-bottom me-2 text-muted"></i> ${act.label}
                </a></li>`;
            }
            if ((act.action === 'api-call' && act.method === 'DELETE') || act.action === 'delete') {
                const url = resolveActionUrl(act, row);
                const msg = act.confirm_message || 'Are you sure?';
                return `<li><a class="dropdown-item" href="javascript:void(0)" onclick="window.deleteItem(event, '${url}', '${msg}')">
                    <i class="${act.icon} align-bottom me-2 text-muted text-danger"></i> ${act.label}
                </a></li>`;
            }
            return '';
        }).join('');

        return `
            <div class="dropdown">
                <button class="btn btn-soft-secondary btn-sm" data-bs-toggle="dropdown" aria-expanded="false">
                    <i class="ri-more-fill"></i>
                </button>
                <ul class="dropdown-menu dropdown-menu-end">${dropdownItems}</ul>
            </div>
        `;
    }

    renderPager() {
        const total = this.filteredData.length;
        const totalPages = Math.ceil(total / this.pageSize);
        const start = (this.currentPage - 1) * this.pageSize + 1;
        const end = Math.min(start + this.pageSize - 1, total);

        const infoEl = this.container.querySelector(`#${this.container.id}-info`);
        if (infoEl) infoEl.innerText = `Showing ${total > 0 ? start : 0} to ${end} of ${total} entries`;

        let html = '';
        if (totalPages > 1) {
            html = `
                <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="window.gridInstances['${this.container.id}'].setPage(${this.currentPage - 1}); return false;">
                        <i class="ri-arrow-left-s-line"></i>
                    </a>
                </li>
            `;

            // Simple logic: Show generic range
            for (let i = 1; i <= totalPages; i++) {
                // Optimization: Only show First, Last, and Current +/- 1
                if (i === 1 || i === totalPages || (i >= this.currentPage - 1 && i <= this.currentPage + 1)) {
                    html += `<li class="page-item ${i === this.currentPage ? 'active' : ''}"><a class="page-link" href="#" onclick="window.gridInstances['${this.container.id}'].setPage(${i}); return false;">${i}</a></li>`;
                } else if (i === this.currentPage - 2 || i === this.currentPage + 2) {
                    html += `<li class="page-item disabled"><a class="page-link" href="#">...</a></li>`;
                }
            }

            html += `
                <li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
                    <a class="page-link" href="#" onclick="window.gridInstances['${this.container.id}'].setPage(${this.currentPage + 1}); return false;">
                        <i class="ri-arrow-right-s-line"></i>
                    </a>
                </li>
            `;
        }

        const pagerEl = this.container.querySelector(`#${this.container.id}-pager`);
        if (pagerEl) pagerEl.innerHTML = html;
    }
}
