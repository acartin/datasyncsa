
import { GridBase } from './GridBase.js';
import { formatters } from './formatters.js';
import { resolveActionUrl, resolveSchemaB64 } from './actionContract.js';

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
            <div class="table-grid-wrapper" style="min-height: 500px; display: flex; flex-direction: column;">
                <div class="d-flex justify-content-between align-items-center mb-3 grid-header-controls">
                    <!-- Filters will inject here -->
                    <div class="grid-header-actions d-flex gap-2"></div>
                    <div id="${this.container.id}-loader" class="text-muted small ms-auto" style="display:none;">Loading...</div>
                </div>
                <div class="table-responsive" style="flex: 1;">
                    <table class="table table-nowrap table-hover align-middle mb-0">
                        <thead class="table-light text-muted">
                            <tr>${this.config.columns.map(c => `
                                <th class="sortable text-uppercase" onclick="window.gridInstances['${this.container.id}'].handleSort('${c.id}')" style="cursor:pointer; font-size:11px; font-weight:600;">
                                    ${c.label || c.name}
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
                            ${c.label || c.name} ${sortIcon}
                        </th>`;
        }).join('')}
                ${this.actions.length > 0 ? '<th style="width: 50px;"></th>' : ''}
            </tr>
        `;

        // 2. Render Body
        const tbodyHtml = rows.map(row => `
            <tr style="cursor: pointer;" onclick="window.gridInstances['${this.container.id}'].handleRowDoubleClick('${row.id}', event)">
                ${this.config.columns.map(col => `<td>${this.renderCell(row, col)}</td>`).join('')}
                ${this.actions.length > 0 ? `<td>${this.renderActions(row)}</td>` : ''}
            </tr>
        `).join('');

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

        const buttons = this.headerActions.map(act => {
            const schemaToPass = resolveSchemaB64(act, {
                formSchema: this.config.form_schema,
                fallbackSchema: this.schemaStr
            });

            // If action is modal-form creation, url usually doesn't need ID replacement
            const url = resolveActionUrl(act);
            const modalTitle = act.modal_title || act.label;
            const color = act.color || 'primary';
            const icon = act.icon || 'ri-add-line';

            // We reuse handleEditAction but passing empty ID ('') or handled differently?
            // Usually handleEditAction does: renderModalForm(title, schema, url, id)
            // If id is missing, renderModalForm treats it as Create (POST).

            return `
                <button class="btn btn-${color} btn-sm waves-effect waves-light" 
                    onclick="window.handleEditAction(event, '', '${url}', '${schemaToPass}', '${modalTitle}')">
                    <i class="${icon} me-1 align-bottom"></i> ${act.label}
                </button>
            `;
        }).join('');

        container.innerHTML = buttons;
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
            return `<div class="d-flex align-items-center gap-2">
                <div style="width: 24px; height: 24px; border-radius: 4px; background-color: ${cellValue}; border: 1px solid rgba(0,0,0,0.1);"></div>
                <span class="text-muted small">${cellValue}</span>
            </div>`;
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
