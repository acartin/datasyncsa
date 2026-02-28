/**
 * GridFilters - Filter management for CustomGrid
 * Handles search, column filters, and visual filter pills
 */
import { resolveActionUrl, resolveSchemaB64 } from './actionContract.js';

function cssVar(name, fallback = '') {
    if (typeof window === 'undefined' || !window.getComputedStyle) return fallback;
    const value = window.getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
}

function getSwalThemeOptions() {
    return {
        background: cssVar('--vz-body-bg', 'var(--vz-body-bg)'),
        color: cssVar('--vz-body-color', 'var(--vz-body-color)'),
    };
}

function getSwalActionColors() {
    return {
        confirmButtonColor: cssVar('--ac-color-danger', 'var(--ac-color-danger)'),
        cancelButtonColor: cssVar('--ac-color-muted', 'var(--ac-color-muted)'),
    };
}

class GridFilters {
    constructor(grid) {
        this.grid = grid;
        this.config = grid.config.filterConfig || {};
        this.gridId = grid.config.grid_id || 'default';
        this.activeFilters = {
            search: null,
            columns: {}
        };
        this.presets = [];
        this.currentPresetId = null;

        // Load presets on initialization
        this.loadPresets();
    }

    /**
     * Helper to show theme-aware toasts
     */
    showToast(icon, title, text) {
        if (!window.Swal) return;

        window.Swal.fire({
            icon: icon,
            title: title,
            text: text,
            timer: 2000,
            showConfirmButton: false,
            position: 'top-end',
            toast: true,
            ...getSwalThemeOptions()
        });
    }

    /**
     * Fetch presets from backend
     */
    async loadPresets() {
        try {
            const response = await fetch(`${window.AppConfig.API_BASE_URL}/grid-presets/${this.gridId}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });
            if (response.ok) {
                this.presets = await response.json();
                this.renderFilterBar(); // Re-render to show presets
            }
        } catch (error) {
            console.error('[GridFilters] Error loading presets:', error);
        }
    }

    /**
     * Render the filter bar UI
     */
    renderFilterBar() {
        const html = `
            <div class="filter-bar mb-3">
                <div class="d-flex flex-column flex-md-row gap-2 align-items-stretch align-items-md-center grid-filter-topbar">
                    <div class="grid-filter-search flex-grow-1 grid-filter-search-min">
                        <div class="search-box position-relative">
                            <input type="text" 
                                   class="form-control search ps-5" 
                                   placeholder="Buscar por nombre o email..."
                                   id="grid-search-${this.grid.container.id}">
                            <i class="ri-search-line search-icon position-absolute top-50 start-0 translate-middle-y ms-3 text-muted"></i>
                        </div>
                    </div>
                    <div class="grid-filter-actions">
                        <div class="d-flex flex-wrap justify-content-md-end justify-content-start align-items-center gap-2">
                        <div class="dropdown">
                            <button class="btn btn-ghost-secondary btn-sm fs-13 fw-normal dropdown-toggle text-body" type="button" data-bs-toggle="dropdown">
                                <i class="icon"></i> Vistas
                            </button>
                            <div class="dropdown-menu dropdown-menu-end grid-filter-dropdown-menu">
                                <h6 class="dropdown-header fs-11 text-muted text-uppercase fw-semibold">Vistas Guardadas</h6>
                                ${this.presets.length > 0 ? this.presets.map(p => {
            // Check if icon is a Remix Icon class or emoji
            const iconHtml = p.icon && p.icon.startsWith('ri-')
                ? `<i class="${p.icon} me-1 align-middle fs-16"></i>`
                : (p.icon || '📁');

            return `
                                    <div class="dropdown-item-wrapper position-relative grid-preset-item-wrapper">
                                        <a class="dropdown-item d-flex justify-content-between align-items-center fs-13 fw-normal py-2 pe-5" 
                                           href="javascript:void(0);" 
                                           onclick="window.gridInstances['${this.grid.container.id}'].filters.applyPreset('${p.id}')">
                                            <span>${iconHtml} <span class="ms-1">${p.name}</span></span>
                                            ${p.is_default ? '<span class="badge bg-success-subtle text-success ms-2 fs-10 fw-semibold text-uppercase">Pre-determinada</span>' : ''}
                                        </a>
                                        <button class="btn btn-sm btn-ghost-danger delete-preset-btn grid-preset-delete-btn position-absolute end-0 top-50 translate-middle-y me-2" 
                                                onclick="event.stopPropagation(); window.gridInstances['${this.grid.container.id}'].filters.deletePreset('${p.id}', '${p.name}')">
                                            <i class="ri-delete-bin-line"></i>
                                        </button>
                                    </div>
                                `}).join('') : '<div class="dropdown-item text-muted">No hay vistas guardadas</div>'}
                                <div class="border-top mt-2">
                                    <a class="dropdown-item fs-13 fw-normal py-2" href="javascript:void(0);"
                                       onclick="window.gridInstances['${this.grid.container.id}'].filters.openSavePresetModal()">
                                        <i class="icon ri-save-line me-2 align-middle text-muted"></i> <span>Guardar Vista Actual</span>
                                    </a>
                                </div>
                            </div>
                        </div>

                        <button class="btn btn-ghost-secondary btn-sm fs-13 fw-normal text-body" 
                                onclick="window.gridInstances['${this.grid.container.id}'].filters.openFilterPanel()">
                            <i class="icon"></i> Filtros
                        </button>
                        ${this.hasActiveFilters() ? `
                        <button class="btn btn-ghost-danger btn-sm fs-13 fw-normal text-danger" 
                                onclick="window.gridInstances['${this.grid.container.id}'].filters.clearAllFilters()">
                            <i class="icon"></i> Limpiar
                        </button>
                        ` : ''}

                        <!-- Header Actions (Injected via SDUI) -->
                        ${this.renderHeaderActionsHtml()}
                        </div>
                    </div>
                </div>
                <div id="active-filters-${this.grid.container.id}" class="mt-2"></div>
            </div>
        `;

        // Update container content instead of insertAdjacentHTML if already exists
        const existingBar = this.grid.container.querySelector('.filter-bar');
        if (existingBar) {
            existingBar.outerHTML = html;
        } else {
            this.grid.container.insertAdjacentHTML('afterbegin', html);
        }

        this.attachEvents();
        this.renderActivePills();
    }

    /**
     * Generate HTML for Header Actions (Create Buttons)
     */
    renderHeaderActionsHtml() {
        const actions = this.grid.config.header_actions || [];
        if (actions.length === 0) return '';

        return actions.map(act => {
            const schemaToPass = resolveSchemaB64(act, {
                formSchema: this.grid.config.form_schema
            });
            const url = resolveActionUrl(act);
            const modalTitle = act.modal_title || act.label;
            const color = act.color || 'primary'; // Create actions usually primary
            const icon = act.icon || 'ri-add-line';

            return `
                <button class="btn btn-${color} btn-sm fs-13 fw-normal shadow-sm" 
                    onclick="window.handleEditAction(event, '', '${url}', '${schemaToPass}', '${modalTitle}')">
                    <i class="icon ${icon} me-1 align-bottom"></i> ${act.label}
                </button>
            `;
        }).join('');
    }

    /**
     * Attach event listeners
     */
    attachEvents() {
        const searchInput = document.getElementById(`grid-search-${this.grid.container.id}`);
        if (searchInput) {
            // Debounce search
            let timeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    this.setSearchFilter(e.target.value);
                }, 300);
            });
        }
    }

    /**
     * Set search filter
     */
    setSearchFilter(term) {
        this.activeFilters.search = term && term.trim() ? term.trim() : null;
        this.applyFilters();
        this.renderActivePills();
    }

    /**
     * Add column filter
     */
    addColumnFilter(columnId, value) {
        if (!this.activeFilters.columns[columnId]) {
            this.activeFilters.columns[columnId] = [];
        }

        if (!this.activeFilters.columns[columnId].includes(value)) {
            this.activeFilters.columns[columnId].push(value);
        }

        this.applyFilters();
        this.renderActivePills();
    }

    /**
     * Remove column filter
     */
    removeColumnFilter(columnId, value = null) {
        if (value === null) {
            delete this.activeFilters.columns[columnId];
        } else {
            const index = this.activeFilters.columns[columnId]?.indexOf(value);
            if (index > -1) {
                this.activeFilters.columns[columnId].splice(index, 1);
                if (this.activeFilters.columns[columnId].length === 0) {
                    delete this.activeFilters.columns[columnId];
                }
            }
        }

        this.applyFilters();
        this.renderActivePills();
    }

    /**
     * Clear all filters
     */
    clearAllFilters() {
        this.activeFilters = {
            search: null,
            columns: {}
        };

        const searchInput = document.getElementById(`grid-search-${this.grid.container.id}`);
        if (searchInput) searchInput.value = '';

        this.applyFilters();
        this.renderActivePills();
        this.renderFilterBar(); // Re-render to update buttons
    }

    /**
     * Check if there are active filters
     */
    hasActiveFilters() {
        return this.activeFilters.search || Object.keys(this.activeFilters.columns).length > 0;
    }

    /**
     * Render active filter pills
     */
    renderActivePills() {
        const container = document.getElementById(`active-filters-${this.grid.container.id}`);
        if (!container) return;

        let pillsHtml = '';

        // Search pill
        if (this.activeFilters.search) {
            pillsHtml += `
                <div class="d-inline-flex align-items-center py-1 px-2 border rounded bg-light text-body fs-13 me-2 mb-2">
                    <i class="icon ri-search-line me-2 text-muted"></i>
                    <span>Búsqueda: "${this.activeFilters.search}"</span>
                    <button type="button" class="btn-close btn-close-sm ms-2" 
                            onclick="window.gridInstances['${this.grid.container.id}'].filters.setSearchFilter('')"
                            aria-label="Close"></button>
                </div>
            `;
        }

        // Column filter pills
        for (const [columnId, values] of Object.entries(this.activeFilters.columns)) {
            const column = this.config.filterableColumns?.find(c => c.id === columnId);
            if (!column) continue;

            for (const value of values) {
                pillsHtml += this.renderFilterPill(columnId, value, column);
            }
        }

        container.innerHTML = pillsHtml || '';
    }

    /**
     * Render a single filter pill
     */
    renderFilterPill(columnId, value, column) {
        return `
            <div class="d-inline-flex align-items-center py-1 px-2 border rounded bg-light text-body fs-13 me-2 mb-2">
                <i class="icon ${column.icon} me-2 text-muted"></i>
                <span>${column.label}: <strong>${value}</strong></span>
                <button type="button" class="btn-close btn-close-sm ms-2" 
                        onclick="window.gridInstances['${this.grid.container.id}'].filters.removeColumnFilter('${columnId}', '${value}')"
                        aria-label="Close"></button>
            </div>
        `;
    }

    /**
     * Open filter panel (modal)
     */
    openFilterPanel() {
        // Get unique values and their colors for each filterable column
        const columnOptions = {};

        this.config.filterableColumns?.forEach(column => {
            const optionsMap = new Map(); // label -> {color, score, icon}
            this.grid.data.forEach(row => {
                const cellData = row[column.id];
                if (!cellData) return;

                let label, color, score, icon;

                if (typeof cellData === 'object') {
                    label = cellData.label;
                    color = cellData.color || 'secondary';
                    score = cellData.score !== undefined ? cellData.score : 0;
                    icon = cellData.icon || 'ri-checkbox-blank-circle-fill';
                } else if (typeof cellData === 'string') {
                    label = cellData;
                    color = 'secondary';
                    score = 0;
                    icon = 'ri-checkbox-blank-circle-fill';
                }

                if (label && label !== 'NULO' && label !== 'PENDIENTE' && label !== '-' && label !== 'N/A') {
                    if (!optionsMap.has(label)) {
                        optionsMap.set(label, { color, score, icon });
                    }
                }
            });
            // Convert to array and sort by SCORE (Descending: High score first)
            columnOptions[column.id] = Array.from(optionsMap.entries())
                .map(([label, info]) => ({ label, color: info.color, score: info.score, icon: info.icon }))
                .sort((a, b) => b.score - a.score);
        });

        // Build modal HTML
        const modalHtml = `
            <div class="modal fade" id="filterModal-${this.grid.container.id}" tabindex="-1">
                   <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="icon ri-filter-line me-2"></i>Filtros Avanzados
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body p-4">
                            <div class="filter-groups-container d-flex flex-wrap grid-filter-groups">
                                ${this.config.filterableColumns?.map(column => {
            const options = columnOptions[column.id] || [];
            if (options.length === 0) return '';

            return `
                                        <div class="filter-group-item grid-filter-group-item">
                                            <h6 class="text-muted mb-4 fs-15 text-uppercase fw-semibold d-flex align-items-center">
                                                <i class="icon ${column.icon} me-2 fs-24 text-primary"></i>${column.label}
                                            </h6>
                                            <div class="filter-options-list px-2">
                                                ${options.map(opt => {
                const isChecked = this.activeFilters.columns[column.id]?.includes(opt.label);
                const colorClass = opt.color.startsWith('thermal-') ? opt.color : `text-${opt.color}`;

                return `
                                                        <div class="form-check mb-3 d-flex align-items-center custom-check-thermal">
                                                            <input class="form-check-input me-3" 
                                                                   type="checkbox" 
                                                                   id="filter-${column.id}-${opt.label.replace(/\s+/g, '-')}"
                                                                   data-column="${column.id}"
                                                                   data-value="${opt.label}"
                                                                   ${isChecked ? 'checked' : ''}>
                                                            <label class="form-check-label fs-13 fw-normal d-flex align-items-center m-0 p-0" 
                                                                   for="filter-${column.id}-${opt.label.replace(/\s+/g, '-')}">
                                                                <i class="${opt.icon} me-2 fs-20 ${colorClass} align-middle grid-filter-opt-icon"></i> 
                                                                <span class="text-body">${opt.label}</span>
                                                            </label>
                                                        </div>
                                                    `;
            }).join('')}
                                            </div>
                                        </div>
                                    `;
        }).join('')}
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-light" data-bs-dismiss="modal">
                                Cancelar
                            </button>
                            <button type="button" class="btn btn-primary" id="applyFilters-${this.grid.container.id}">
                                <i class="icon ri-check-line me-1"></i>Aplicar Filtros
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if any
        const existingModal = document.getElementById(`filterModal-${this.grid.container.id}`);
        if (existingModal) existingModal.remove();

        // Append modal to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Show modal
        const modalElement = document.getElementById(`filterModal-${this.grid.container.id}`);
        const modal = new bootstrap.Modal(modalElement);
        modal.show();

        // Attach event listener to apply button
        document.getElementById(`applyFilters-${this.grid.container.id}`).addEventListener('click', () => {
            this.applyModalFilters();
            modal.hide();
        });

        // Clean up modal after hide
        modalElement.addEventListener('hidden.bs.modal', () => {
            modalElement.remove();
        });
    }

    /**
     * Apply filters from modal
     */
    applyModalFilters() {
        const modalElement = document.getElementById(`filterModal-${this.grid.container.id}`);
        const checkboxes = modalElement.querySelectorAll('.form-check-input:checked');

        // Clear existing column filters
        this.activeFilters.columns = {};

        // Add selected filters
        checkboxes.forEach(checkbox => {
            const columnId = checkbox.dataset.column;
            const value = checkbox.dataset.value;

            if (!this.activeFilters.columns[columnId]) {
                this.activeFilters.columns[columnId] = [];
            }
            this.activeFilters.columns[columnId].push(value);
        });

        this.applyFilters();
        this.renderActivePills();
        this.renderFilterBar(); // Re-render to update "Limpiar" button
    }

    /**
     * Apply all active filters to grid data
     */
    applyFilters() {
        let filtered = [...this.grid.data];

        // Apply search filter (Exact Phrase Match with Normalization)
        if (this.activeFilters.search) {
            // Helper: Remove punctuation/accents and keep only alphanumeric + spaces
            const normalize = (str) => {
                return str.toLowerCase()
                    .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // Remove accents
                    .replace(/[^\w\s]/gi, ' ') // Replace punctuation with space
                    .replace(/\s+/g, ' ') // Collapse multiple spaces
                    .trim();
            };

            const rawTerm = normalize(this.activeFilters.search);
            // const searchTokens = rawTerm.split(' ').filter(t => t.length > 0); // REMOVED TOKEN SPLITTING

            let searchFields = this.config.searchFields;

            // If no search fields defined, dynamic fallback to all visible text columns
            if (!searchFields && this.grid.config.columns) {
                searchFields = this.grid.config.columns
                    .filter(c => !c.hidden && (c.type === 'text' || !c.type))
                    .map(c => c.id);
            }
            // Absolute fallback
            if (!searchFields || searchFields.length === 0) {
                searchFields = ['name', 'email', 'full_name', 'label'];
            }

            filtered = filtered.filter(row => {
                // Combine and normalize row data
                const rowSearchString = normalize(
                    searchFields.map(field => {
                        const val = row[field];
                        return val ? val.toString() : '';
                    }).join(' ')
                );

                // Check if the EXACT normalized phrase exists in the row
                return rowSearchString.includes(rawTerm);
            });
        }

        // Apply column filters
        for (const [columnId, values] of Object.entries(this.activeFilters.columns)) {
            filtered = filtered.filter(row => {
                const cellData = row[columnId];
                const cellValue = cellData?.label || cellData;
                return values.includes(cellValue);
            });
        }

        this.grid.filteredData = filtered;
        this.grid.currentPage = 1; // Reset to first page
        this.grid.render();
    }

    /**
     * Apply a saved preset by ID
     */
    applyPreset(presetId) {
        const preset = this.presets.find(p => p.id === presetId);
        if (!preset) return;


        // Reset current filters first
        this.activeFilters = {
            search: null,
            columns: {}
        };

        // Apply from config
        if (preset.config.filters) {
            this.activeFilters.search = preset.config.filters.search || null;
            this.activeFilters.columns = { ...preset.config.filters.columns };
        }

        // Update search input visually
        const searchInput = document.getElementById(`grid-search-${this.grid.container.id}`);
        if (searchInput) {
            searchInput.value = this.activeFilters.search || '';
        }

        this.currentPresetId = presetId;
        this.applyFilters();
        this.renderActivePills();
        this.renderFilterBar();

        // Show success notification
        this.showToast('success', 'Vista Aplicada', `Se ha cargado la vista: ${preset.name}`);
    }

    /**
     * Get current filter state (for saving views)
     */
    getFilterState() {
        return {
            search: this.activeFilters.search,
            columns: { ...this.activeFilters.columns }
        };
    }

    /**
     * Open modal to save current filters as a preset
     */
    openSavePresetModal() {
        const availableIcons = [
            { icon: 'ri-flag-fill', color: 'danger' },
            { icon: 'ri-star-fill', color: 'warning' },
            { icon: 'ri-heart-fill', color: 'danger' },
            { icon: 'ri-fire-fill', color: 'orange' },
            { icon: 'ri-flashlight-fill', color: 'info' },
            { icon: 'ri-shield-fill', color: 'primary' },
            { icon: 'ri-rocket-fill', color: 'success' },
            { icon: 'ri-magic-line', color: 'info' },
            { icon: 'ri-vip-diamond-fill', color: 'primary' },
            { icon: 'ri-trophy-fill', color: 'warning' },
            { icon: 'ri-bookmark-fill', color: 'primary' },
            { icon: 'ri-price-tag-3-fill', color: 'success' },
            { icon: 'ri-leaf-fill', color: 'success' },
            { icon: 'ri-thunderstorm-fill', color: 'info' },
            { icon: 'ri-sun-fill', color: 'warning' },
            { icon: 'ri-moon-fill', color: 'secondary' },
            { icon: 'ri-ghost-fill', color: 'secondary' },
            { icon: 'ri-anchor-fill', color: 'primary' },
            { icon: 'ri-lightbulb-fill', color: 'warning' },
            { icon: 'ri-send-plane-fill', color: 'success' },
            { icon: 'ri-earth-fill', color: 'info' }
        ];

        let selectedIcon = availableIcons[0].icon;

        const modalHtml = `
            <div class="modal fade" id="savePresetModal-${this.grid.container.id}" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="ri-save-line me-2"></i>Guardar Vista
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body p-4">
                            <div class="mb-4">
                                <label class="form-label fs-13 fw-semibold text-muted">Nombre de la vista</label>
                                <input type="text" class="form-control form-control-lg fs-15" id="preset-name-${this.grid.container.id}" placeholder="Ej: Leads Calientes 🔥">
                            </div>
                            
                            <div class="mb-4">
                                <label class="form-label fs-13 fw-semibold text-muted mb-3">Selecciona un Icono</label>
                                <div class="d-flex flex-wrap gap-2 icon-selector-grid">
                                    ${availableIcons.map((item, idx) => `
                                        <div class="grid-icon-option ${idx === 0 ? 'active' : ''} text-${item.color}" 
                                             data-icon="${item.icon}"
                                             onclick="window.gridInstances['${this.grid.container.id}'].filters.selectPresetIcon(this)">
                                            <i class="${item.icon}"></i>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>

                            <div class="form-check form-switch mb-2">
                                <input class="form-check-input" type="checkbox" id="preset-default-${this.grid.container.id}">
                                <label class="form-check-label fs-13" for="preset-default-${this.grid.container.id}">
                                    Establecer como vista predeterminada
                                </label>
                            </div>
                        </div>
                        <div class="modal-footer bg-light">
                            <button type="button" class="btn btn-ghost-danger" data-bs-dismiss="modal">Cancelar</button>
                            <button type="button" class="btn btn-primary px-4" id="btn-save-preset-${this.grid.container.id}">
                                <i class="ri-save-line me-1"></i>Guardar Vista
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Define selection helper globally for this session
        this.selectPresetIcon = (element) => {
            const container = element.closest('.icon-selector-grid');
            container.querySelectorAll('.grid-icon-option').forEach(opt => opt.classList.remove('active'));
            element.classList.add('active');

            // Store full class: "ri-icon-name text-color"
            const iconClass = element.dataset.icon;
            const colorClass = Array.from(element.classList).find(c => c.startsWith('text-')) || 'text-primary';
            selectedIcon = `${iconClass} ${colorClass}`;
        };

        const modalElement = document.getElementById(`savePresetModal-${this.grid.container.id}`);
        const modal = new bootstrap.Modal(modalElement);
        modal.show();

        document.getElementById(`btn-save-preset-${this.grid.container.id}`).addEventListener('click', () => {
            const name = document.getElementById(`preset-name-${this.grid.container.id}`).value;
            const isDefault = document.getElementById(`preset-default-${this.grid.container.id}`).checked;

            if (name) {
                // Ensure we use the icon with the 'ri-' prefix or as a full class
                this.saveCurrentPreset(name, selectedIcon, isDefault);
                modal.hide();
            } else {
                this.showToast('error', 'Error', 'Por favor ingresa un nombre para la vista.');
            }
        });

        modalElement.addEventListener('hidden.bs.modal', () => modalElement.remove());
    }

    /**
     * Save current filter state to backend
     */
    async saveCurrentPreset(name, icon, isDefault) {
        const presetData = {
            name: name,
            icon: icon || '📁',
            grid_id: this.gridId,
            is_default: isDefault,
            config: {
                filters: this.getFilterState()
            }
        };

        try {
            const response = await fetch(`${window.AppConfig.API_BASE_URL}/grid-presets`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify(presetData)
            });

            if (response.ok) {
                this.showToast('success', 'Vista Guardada', `La vista "${name}" ha sido guardada correctamente.`);
                await this.loadPresets(); // Reload list
            } else {
                console.error('[GridFilters] Failed to save preset');
                if (window.Swal) {
                    window.Swal.fire({
                        icon: 'error',
                        title: 'Error al Guardar',
                        text: 'No se pudo guardar la vista. Por favor intenta de nuevo.',
                        ...getSwalThemeOptions()
                    });
                }
            }
        } catch (error) {
            console.error('[GridFilters] Error saving preset:', error);
        }
    }

    /**
     * Delete a preset with confirmation
     */
    async deletePreset(presetId, presetName) {
        if (!window.Swal) {
            if (!confirm(`¿Estás seguro de eliminar la vista "${presetName}"?`)) {
                return;
            }
        } else {
            const result = await window.Swal.fire({
                title: '¿Eliminar Vista?',
                html: `¿Estás seguro de que deseas eliminar la vista <strong>"${presetName}"</strong>?<br><small class="text-muted">Esta acción no se puede deshacer.</small>`,
                icon: 'warning',
                showCancelButton: true,
                ...getSwalActionColors(),
                confirmButtonText: '<i class="ri-delete-bin-line me-1"></i> Sí, Eliminar',
                cancelButtonText: 'Cancelar',
                ...getSwalThemeOptions()
            });

            if (!result.isConfirmed) {
                return;
            }
        }

        try {
            const response = await fetch(`${window.AppConfig.API_BASE_URL}/grid-presets/${presetId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });

            if (response.ok) {
                this.showToast('success', 'Vista Eliminada', `La vista "${presetName}" ha sido eliminada.`);
                await this.loadPresets(); // Reload list
            } else {
                this.showToast('error', 'Error', 'No se pudo eliminar la vista.');
            }
        } catch (error) {
            console.error('[GridFilters] Error deleting preset:', error);
            this.showToast('error', 'Error', 'Ocurrió un error al eliminar la vista.');
        }
    }
}

// Export for use in CustomGrid
export { GridFilters };
window.GridFilters = GridFilters; // Also expose globally for inline handlers
