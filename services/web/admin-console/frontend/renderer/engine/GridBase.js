
import { GridFilters } from './GridFilters.js';
import { resolveActionUrl, resolveSchemaB64 } from './actionContract.js';

/**
 * GridBase - Foundation class for custom grids
 * Encapsulates:
 * 1. Global Registry & Lifecycle
 * 2. Data Pipeline (Fetch -> Filter -> Sort)
 * 3. Pagination Logic
 * 4. Filter Integration
 */
export class GridBase {
    constructor(container, config) {
        this.container = container;
        this.config = config;



        // Core State
        this.data = [];
        this.filteredData = [];
        this.currentPage = 1;
        this.pageSize = config.pageSize || 10;
        this.sortState = { colId: null, direction: 'asc' };
        this.pollingInterval = null;
        this.lastDataSignature = null;
        this.selectedRowId = null;

        // 1. Registry
        this.registerInstance();

        // 2. Filters
        if (this.config.enableFilters) {
            this.filters = new GridFilters(this);
        }
    }

    registerInstance() {
        window.gridInstances = window.gridInstances || {};
        if (this.container.id) {
            window.gridInstances[this.container.id] = this;
            // console.log(`[${this.constructor.name}] Registered instance: ${this.container.id}`);
        } else {
            console.warn(`[${this.constructor.name}] Container has no ID, cannot register instance!`);
        }
    }

    async init() {
        try {
            this.renderSkeleton();
            await this.fetchData();

            if (this.filters) this.filters.renderFilterBar();

            this.applySort();
            this.render();

            // Setup Polling if enabled
            if (this.config.polling && !this.pollingInterval) {
                const interval = parseInt(this.config.polling);
                if (interval > 0) {
                    this.pollingInterval = setInterval(() => {
                        // Solo refrescar si el elemento sigue en el DOM
                        if (document.getElementById(this.container.id)) {
                            this.fetchData({ silent: true }).then((changed) => {
                                // No re-render si no hay cambios reales en datos
                                if (!changed) return;

                                // Si hay filtros activos, applyFilters() ya renderiza internamente.
                                if (this.filters && this.filters.hasActiveFilters()) return;

                                this.applySort();
                                this.render();
                            });
                        } else {
                            this.stopPolling();
                        }
                    }, interval);
                }
            }
        } catch (e) {
            console.error(`[${this.constructor.name}] Init Error:`, e);
            this.container.innerHTML = `<div class="p-3 text-danger">Error initializing grid: ${e.message}</div>`;
        }
    }

    // Core Data Pipeline
    async fetchData(options = {}) {
        const silent = Boolean(options.silent);
        if (!silent) this.toggleLoader(true);

        const token = localStorage.getItem('access_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

        try {
            // Append version/timestamp to avoid cache if needed, simplified here
            const url = `${window.AppConfig.API_BASE_URL}${this.config.data_url}`;
            const res = await fetch(url, { headers });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const json = await res.json();

            // Handle unwrapping of common API response patterns
            let nextData = [];
            if (Array.isArray(json)) {
                nextData = json;
            } else if (json.data && Array.isArray(json.data)) {
                nextData = json.data;
            } else if (json.results && Array.isArray(json.results)) {
                nextData = json.results;
            } else if (json.items && Array.isArray(json.items)) {
                nextData = json.items;
            } else {
                console.warn(`[${this.constructor.name}] API response is not an array`, json);
                nextData = [];
            }

            const nextSignature = this.buildDataSignature(nextData);
            const changed = nextSignature !== this.lastDataSignature;
            if (!changed && silent) return false;

            this.lastDataSignature = nextSignature;
            this.data = nextData;
            this.filteredData = [...this.data];

            // Re-apply filters if they exist (e.g. on refresh)
            if (this.filters && this.filters.hasActiveFilters()) {
                this.filters.applyFilters();
            }

            return true;
        } catch (e) {
            throw e; // Propagate to init/forceRender
        } finally {
            if (!silent) this.toggleLoader(false);
        }
    }

    buildDataSignature(rows) {
        // Stable signature to avoid false positives caused by row/key ordering differences.
        const configuredRowKey = this.config.row_key || '';
        const compareFields = Array.isArray(this.config.polling_compare_fields)
            ? this.config.polling_compare_fields.filter(Boolean)
            : [];

        const sortKeyForRow = (row) => {
            if (!row || typeof row !== 'object') return '';
            if (configuredRowKey && row[configuredRowKey] !== undefined && row[configuredRowKey] !== null) {
                return String(row[configuredRowKey]);
            }
            return String(row.id ?? row.content_id ?? row.filename ?? row.url ?? '');
        };

        const normalize = (value) => {
            if (Array.isArray(value)) {
                return value.map(normalize);
            }
            if (value && typeof value === 'object') {
                const out = {};
                Object.keys(value).sort().forEach((k) => {
                    out[k] = normalize(value[k]);
                });
                return out;
            }
            return value;
        };

        const rowsForSignature = compareFields.length > 0
            ? rows.map((row) => {
                const slim = {};
                const rowKey = configuredRowKey || 'id';
                slim[rowKey] = row?.[configuredRowKey] ?? row?.id ?? row?.content_id ?? row?.filename ?? row?.url ?? null;
                compareFields.forEach((field) => {
                    slim[field] = row?.[field];
                });
                return slim;
            })
            : rows;

        const sortedRows = [...rowsForSignature].sort((a, b) => {
            const ka = sortKeyForRow(a);
            const kb = sortKeyForRow(b);
            return ka.localeCompare(kb);
        });

        return JSON.stringify(normalize(sortedRows));
    }

    toggleLoader(show) {
        const loader = document.getElementById(`${this.container.id}-loader`);
        if (loader) loader.style.display = show ? 'block' : 'none';
    }

    // Sorting Logic
    handleSort(colId) {
        this.applySort(colId);
        this.render();
    }

    applySort(colId = null) {
        if (colId) {
            if (this.sortState.colId === colId) {
                this.sortState.direction = this.sortState.direction === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortState.colId = colId;
                this.sortState.direction = 'desc';
            }
        }

        if (!this.sortState.colId) return;

        const colDef = this.config.columns.find(c => c.id === this.sortState.colId);
        // Fail-safe if column definition not found
        if (!colDef) return;

        const dir = this.sortState.direction === 'asc' ? 1 : -1;

        this.filteredData.sort((a, b) => {
            const valA = this.getSortValue(a, colDef);
            const valB = this.getSortValue(b, colDef);
            if (valA < valB) return -1 * dir;
            if (valA > valB) return 1 * dir;
            return 0;
        });

        this.currentPage = 1; // Reset to first page on sort
    }

    // Hook for children to override
    getSortValue(row, col) {
        const val = row[col.id];
        return (typeof val === 'string') ? val.toLowerCase() : (val || 0);
    }

    // Pagination Logic
    setPage(p) {
        this.currentPage = p;
        this.render();
    }

    getPaginatedRows() {
        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;
        return this.filteredData.slice(start, end);
    }

    // Interaction Handlers
    handleRowClick(rowId, event) {
        if (!rowId) return;

        if (event && (
            event.target.closest('button') ||
            event.target.closest('a') ||
            event.target.closest('.dropdown') ||
            event.target.closest('input')
        )) {
            return;
        }

        this.selectedRowId = rowId;
        this.render();

        if (this.config.navigate_on_click) {
            const row = this.data.find((item) => String(item?.id ?? '') === String(rowId));
            if (row) {
                const navigateAction = this.config.actions?.find((a) => a.action === 'navigate');
                const navigateUrlTemplate = this.config.navigate_url;
                const url = navigateUrlTemplate
                    ? resolveActionUrl({ action_url: navigateUrlTemplate }, row)
                    : (navigateAction ? resolveActionUrl(navigateAction, row) : '');
                if (url && window.navigateTo) {
                    window.navigateTo(url);
                }
            }
        }
    }

    handleRowDoubleClick(rowId, event) {
        if (!rowId) return;

        // Prevent firing if clicked on interactive elements (buttons, links, inputs)
        if (event && (
            event.target.closest('button') ||
            event.target.closest('a') ||
            event.target.closest('.dropdown') ||
            event.target.closest('input')
        )) {
            return;
        }

        // 1. Check for specific double click config
        if (this.config.onDoubleClick) {
            // TODO: Handle custom double click handlers if needed
        }

        // 2. Fallback: Find first 'navigate' action
        let action = this.config.actions?.find(a => a.action === 'navigate');

        // 3. Fallback: Find 'edit' action but trigger ONLY if it's default or no navigate exists
        if (!action) {
            action = this.config.actions?.find(a => a.action === 'edit' || a.action === 'modal-form');
        }

        if (action) {
            const url = resolveActionUrl(action, { id: rowId });

            if (action.action === 'navigate') {
                window.navigateTo(url);
            } else if (action.action === 'modal-form' || action.action === 'edit') {
                const schemaToPass = resolveSchemaB64(action, {
                    formSchema: this.config.form_schema,
                    fallbackSchema: this.container.dataset.schema
                });

                if (window.handleEditAction) {
                    const mockEvent = {
                        preventDefault: () => { },
                        stopPropagation: () => { }
                    };
                    window.handleEditAction(mockEvent, rowId, url, schemaToPass);
                }
            }
        } else {
            // console.log(`[GridBase] No default action found for double click on ${rowId}`);
        }
    }

    // Force Refresh
    async forceRender() {
        // console.log(`[${this.constructor.name}] Force rendering: ${this.container.id}`);
        await this.fetchData();
        this.applySort();
        this.render();
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    // ABSTRACT METHODS
    render() { throw new Error("Method 'render()' must be implemented."); }
    renderSkeleton() { }
}
