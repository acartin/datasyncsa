
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
                            this.fetchData().then(() => {
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
    async fetchData() {
        this.toggleLoader(true);

        const token = localStorage.getItem('access_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

        try {
            // Append version/timestamp to avoid cache if needed, simplified here
            const url = `${window.AppConfig.API_BASE_URL}${this.config.data_url}`;
            const res = await fetch(url, { headers });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const json = await res.json();

            // Handle unwrapping of common API response patterns
            if (Array.isArray(json)) {
                this.data = json;
            } else if (json.data && Array.isArray(json.data)) {
                this.data = json.data;
            } else if (json.results && Array.isArray(json.results)) {
                this.data = json.results;
            } else if (json.items && Array.isArray(json.items)) {
                this.data = json.items;
            } else {
                console.warn(`[${this.constructor.name}] API response is not an array`, json);
                this.data = [];
            }

            this.filteredData = [...this.data];

            // Re-apply filters if they exist (e.g. on refresh)
            if (this.filters && this.filters.hasActiveFilters()) {
                this.filters.applyFilters();
            }
        } catch (e) {
            throw e; // Propagate to init/forceRender
        } finally {
            this.toggleLoader(false);
        }
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
