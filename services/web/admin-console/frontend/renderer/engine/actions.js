/**
 * Action Handlers Manager
 * Handles forms, deletes, modals, and generic SDUI actions.
 */

import { LinkModalForm, renderFormFromSchema, initJsonEditors, syncJsonEditors, destroyJsonEditors } from '../../components/forms/ModalForm.js';
import { safeAtob, safeBtoa } from '../../utils/base64.js';

const API_BASE_URL = window.AppConfig.API_BASE_URL;

/**
 * Submits a modal form via AJAX.
 */
export async function submitModalForm(event, formId, actionUrl, method = 'POST') {
    if (event) event.preventDefault();

    const form = document.getElementById(formId);
    if (!form) {
        Swal.fire({ title: "Error", text: "No se encontró el formulario.", icon: "error" });
        return;
    }
    const jsonSync = syncJsonEditors(form);
    if (!jsonSync.ok) {
        Swal.fire({ title: "Error", text: jsonSync.message || "JSON inválido.", icon: "error" });
        return;
    }

    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const isMultipart = form.getAttribute('enctype') === 'multipart/form-data';
    const formData = new FormData(form);
    const payload = {};

    // 1. Always build the JSON payload (in case we don't have files)
    for (const [key, value] of formData.entries()) {
        if (value instanceof File) continue; // Skip files in the JSON payload
        payload[key] = value;
    }

    // Handle checkboxes (Explicit true/false for JSON)
    const checkboxes = form.querySelectorAll('input[type="checkbox"]:not(.primary-radio)');
    checkboxes.forEach(cb => { payload[cb.name] = cb.checked; });

    // Handle Repeaters
    const repeaters = form.querySelectorAll('.repeater-container');
    repeaters.forEach(rep => {
        const name = rep.dataset.name;
        const items = [];
        const rows = rep.querySelectorAll('.repeater-item');
        rows.forEach(row => {
            const catId = row.querySelector('.category-select').value;
            const val = row.querySelector('.value-input').value;
            const isPrimary = row.querySelector('.primary-radio').checked;
            if (catId && val) {
                items.push({
                    category_id: parseInt(catId),
                    value: val,
                    is_primary: isPrimary
                });
            }
        });
        payload[name] = items;
    });

    // Keep existing password on edit forms when the field is intentionally left blank.
    if (typeof payload.password === 'string' && payload.password.trim() === '') {
        delete payload.password;
    }

    const resolveBandsCriterionId = () => {
        const current = String(payload.criterion_id || '').trim();
        if (current && !current.includes('{')) return current;

        const activeCrudModal = document.querySelector('.modal.show[data-context-b64]');
        if (activeCrudModal && activeCrudModal.dataset.contextB64) {
            try {
                const context = JSON.parse(safeAtob(activeCrudModal.dataset.contextB64) || '{}');
                const ctxCriterionId = String(context.context_criterion_id || '').trim();
                if (ctxCriterionId) return ctxCriterionId;
            } catch (e) {
                // ignore and continue with URL fallback
            }
        }

        const gridInsideModal = activeCrudModal?.querySelector('.js-grid-visual');
        const dataUrl = gridInsideModal?.dataset?.url || '';
        if (dataUrl) {
            try {
                const parsed = new URL(dataUrl, window.location.origin);
                const byQuery = String(parsed.searchParams.get('criterion_id') || '').trim();
                if (byQuery) return byQuery;
            } catch (e) {
                // ignore invalid URL and return empty
            }
        }

        return '';
    };

    if (actionUrl === '/system/verticals/bands') {
        payload.criterion_id = resolveBandsCriterionId();
    }

    const validateBandPayload = async () => {
        if (actionUrl !== '/system/verticals/bands' || method.toUpperCase() !== 'POST') return true;

        const criterionId = String(payload.criterion_id || '').trim();
        const bandKey = String(payload.band_key || '').trim().toLowerCase();
        const minScore = Number(payload.min_score);
        const maxScore = Number(payload.max_score);

        if (!criterionId) {
            Swal.fire({ title: "Error", text: "criterion_id es requerido para crear banda.", icon: "error" });
            return false;
        }
        if (!Number.isFinite(minScore) || !Number.isFinite(maxScore)) {
            Swal.fire({ title: "Error", text: "Min Score y Max Score deben ser numéricos.", icon: "error" });
            return false;
        }
        if (minScore > maxScore) {
            Swal.fire({ title: "Error", text: "Min Score no puede ser mayor que Max Score.", icon: "error" });
            return false;
        }

        try {
            const res = await fetch(
                `${API_BASE_URL}/system/verticals/bands/data?criterion_id=${encodeURIComponent(criterionId)}`,
                { headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } }
            );
            if (!res.ok) return true;
            const existing = await res.json();
            if (!Array.isArray(existing)) return true;

            const keyConflict = existing.some((b) => String(b.band_key || '').trim().toLowerCase() === bandKey);
            if (keyConflict) {
                Swal.fire({ title: "Error", text: "Band Key ya existe para este criterio.", icon: "error" });
                return false;
            }

            const overlap = existing.some((b) => {
                const bMin = Number(b.min_score);
                const bMax = Number(b.max_score);
                if (!Number.isFinite(bMin) || !Number.isFinite(bMax)) return false;
                return minScore <= bMax && maxScore >= bMin;
            });

            if (overlap) {
                Swal.fire({
                    title: "Error",
                    text: "El rango se cruza con una banda existente en este criterio.",
                    icon: "error"
                });
                return false;
            }
        } catch (e) {
            // If validation check fails, continue and let backend be source of truth.
        }

        return true;
    };

    if (!(await validateBandPayload())) return;

    // 2. Decide if we MUST use multipart (only if files are present)
    const hasFiles = form.querySelectorAll('input[type="file"]').length > 0;

    try {
        const headers = {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        };

        let body;
        if (hasFiles) {
            // Must use FormData for files
            body = formData;
        } else {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify(payload);
        }

        const res = await fetch(`${API_BASE_URL}${actionUrl}`, {
            method: method,
            headers: headers,
            body: body
        });

        if (res.ok) {
            const modalEl = form.closest('.modal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            // Prevent focused descendants from staying active while modal becomes aria-hidden.
            if (document.activeElement && typeof document.activeElement.blur === 'function') {
                document.activeElement.blur();
            }
            modal.hide();

            // Refresh via global event or exported function
            if (window.refreshGrids) window.refreshGrids();

            Swal.fire({
                title: "Success!",
                text: "Data saved successfully!",
                icon: "success",
                customClass: { confirmButton: 'btn btn-primary w-xs me-2 mt-2' },
                buttonsStyling: false
            });
        } else {
            let errorText = "Something went wrong!";
            try {
                const errorData = await res.json();
                // Extract detail message from backend (works for 409, 422, 400, etc)
                if (typeof errorData.detail === 'string') {
                    errorText = errorData.detail;
                } else if (Array.isArray(errorData.detail)) {
                    // For 422 validation errors (FastAPI format)
                    errorText = errorData.detail.map(err => `<b>${err.loc[err.loc.length - 1]}:</b> ${err.msg}`).join('<br>');
                } else {
                    errorText = JSON.stringify(errorData);
                }
            } catch (e) {
                // If JSON parsing fails, use status text
                errorText = `Error ${res.status}: ${res.statusText}`;
            }
            Swal.fire({
                title: "Error",
                html: errorText,
                icon: "error",
                customClass: { confirmButton: 'btn btn-primary w-xs mt-2' },
                buttonsStyling: false
            });
        }
    } catch (e) {
        console.error(e);
        Swal.fire({ title: "System Error", text: e.message, icon: "error" });
    }
}

/**
 * Global Delete item handler.
 */
export async function deleteItem(event, url, confirmMsg) {
    if (event) { event.preventDefault(); event.stopPropagation(); }

    Swal.fire({
        title: "Are you sure?",
        text: confirmMsg || "You won't be able to revert this!",
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Yes, delete it!",
        customClass: { confirmButton: 'btn btn-primary w-xs me-2 mt-2', cancelButton: 'btn btn-danger w-xs mt-2' },
        buttonsStyling: false
    }).then(async (result) => {
        if (result.value) {
            try {
                const res = await fetch(`${API_BASE_URL}${url}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
                });
                if (res.ok) {
                    if (window.refreshGrids) window.refreshGrids();
                    Swal.fire({ title: "Deleted!", icon: "success", customClass: { confirmButton: 'btn btn-primary w-xs mt-2' }, buttonsStyling: false });
                } else {
                    Swal.fire({ title: "Error!", text: "Failed to delete.", icon: "error" });
                }
            } catch (e) {
                Swal.fire({ title: "System Error!", icon: "error" });
            }
        }
    });
}

/**
 * Handle Generic SDUI Actions (Modals, etc)
 */
export function handleGenericAction(btn) {
    const action = btn.dataset.action;
    const url = btn.dataset.url;
    const title = btn.dataset.title;
    const method = btn.dataset.method || 'POST';
    const schemaStr = btn.dataset.schema;

    if (action === 'modal-form' && schemaStr) {
        try {
            let schema = [];
            try { schema = JSON.parse(safeAtob(schemaStr)); } catch (e) { schema = JSON.parse(schemaStr); }
            openGenericModal(schema, url, method, title);
        } catch (e) {
            console.error('Schema Parse Error:', e);
        }
    }
}

/**
 * Generic Modal Opener
 */
export async function openGenericModal(schema, url, method, title, data = {}) {
    const formFields = renderFormFromSchema(schema, data);
    const modalId = `modal-${Math.random().toString(36).substr(2, 9)}`;
    const isLargeTextForm = Array.isArray(schema) && schema.some((field) =>
        field &&
        field.type === 'textarea' &&
        (field.name === 'prompt_template' || Number(field.rows || 0) >= 10)
    );
    const dialogClass = isLargeTextForm ? 'modal-xl modal-dialog-scrollable' : '';
    const dialogStyle = isLargeTextForm ? 'max-width: min(1600px, 96vw);' : '';
    const modalHtml = LinkModalForm(modalId, title, formFields, url, method, dialogClass, dialogStyle);

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const modalEl = document.getElementById(modalId);
    const modal = new bootstrap.Modal(modalEl);
    modalEl.removeAttribute('inert');
    modal.show();

    modalEl.addEventListener('hide.bs.modal', () => {
        const activeEl = document.activeElement;
        if (activeEl && modalEl.contains(activeEl) && typeof activeEl.blur === 'function') {
            activeEl.blur();
        }
        modalEl.setAttribute('inert', '');
    });

    modalEl.addEventListener('hidden.bs.modal', () => {
        destroyJsonEditors(modalEl);
        modalEl.remove();
    });

    // Hydrate selects in the modal
    const selects = modalEl.querySelectorAll('select[data-source]');
    for (const select of selects) {
        await hydrateSelect(select);
    }
    bindDependentSelects(modalEl);
    initJsonEditors(modalEl);
}

/**
 * Specialized Hydration for Selects
 */
function resolveSourceUrl(select) {
    const template = select.dataset.source || '';
    if (!template.includes('{')) return template;
    const form = select.closest('form');
    let missingDependency = false;
    const resolved = template.replace(/\{([^}]+)\}/g, (_match, fieldName) => {
        if (!form) return '';
        const sourceField = form.querySelector(`[name="${fieldName}"]`);
        if (!sourceField) {
            missingDependency = true;
            return '';
        }
        const rawValue = sourceField.type === 'checkbox'
            ? (sourceField.checked ? 'true' : 'false')
            : (sourceField.value || sourceField.dataset.value || '');
        const value = String(rawValue).trim();
        if (!value) {
            missingDependency = true;
            return '';
        }
        return encodeURIComponent(value || '');
    });
    return missingDependency ? '' : resolved;
}

function bindDependentSelects(modalEl) {
    const dependentSelects = modalEl.querySelectorAll('select[data-source][data-depends-on]');
    dependentSelects.forEach((depSelect) => {
        const dependsOn = depSelect.dataset.dependsOn;
        if (!dependsOn) return;
        const sourceField = modalEl.querySelector(`[name="${dependsOn}"]`);
        if (!sourceField) return;
        sourceField.addEventListener('change', async () => {
            depSelect.dataset.value = '';
            await hydrateSelect(depSelect);
        });
    });
}

export async function hydrateSelect(select) {
    const url = resolveSourceUrl(select);
    const initialValue = select.dataset.value || '';
    const placeholder = select.querySelector('option[value=""]')
        ? select.querySelector('option[value=""]').innerText
        : 'Select...';
    select.innerHTML = `<option value="">${placeholder}</option>`;
    if (!url) return;

    try {
        const res = await fetch(`${API_BASE_URL}${url}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!res.ok) {
            console.error(`Select Hydration HTTP Error (${res.status})`, { url });
            return;
        }
        const payload = await res.json();
        const items = Array.isArray(payload)
            ? payload
            : (Array.isArray(payload?.items) ? payload.items : []);

        items.forEach(item => {
            const selected = (String(item.id) === String(initialValue)) ? 'selected' : '';
            select.insertAdjacentHTML('beforeend', `<option value="${item.id}" ${selected}>${item.name || item.label}</option>`);
        });
    } catch (e) {
        console.error('Select Hydration Error:', e);
    }
}

/**
 * Generic Edit Handler
 */
export async function handleEditAction(event, id, urlPattern, schemaStr, modalTitle = "Editar registro") {
    if (event) { event.preventDefault(); event.stopPropagation(); }

    let schema = [];
    if (!schemaStr) {
        console.warn('handleEditAction: No schema provided');
    } else {
        try {
            const decoded = safeAtob(schemaStr);
            schema = JSON.parse(decoded || '[]');
        } catch (e) {
            try { schema = JSON.parse(schemaStr || '[]'); } catch (e2) {
                console.error('handleEditAction: Failed to parse schema:', e2);
                schema = [];
            }
        }
    }

    // CASE 1: CREATE (No ID)
    if (!id) {
        // If creating, we want fields marked as 'readonly' (like 'project') to be editable
        const createSchema = schema.map(f => ({ ...f, readonly: false }));
        openGenericModal(createSchema, urlPattern, 'POST', modalTitle, {});
        return;
    }

    // CASE 2: UPDATE (With ID)
    const fetchUrl = urlPattern.replace('{id}', id);

    try {
        const res = await fetch(`${API_BASE_URL}${fetchUrl}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        if (!res.ok) throw new Error("Fetch failed");
        const data = await res.json();
        openGenericModal(schema, fetchUrl, 'PUT', modalTitle, data);
    } catch (e) {
        console.error('Edit Action Error:', e);
    }
}

export async function handleCreateAction(event, actionUrl, schemaStr, modalTitle = "Nuevo registro", prefillB64 = "") {
    if (event) { event.preventDefault(); event.stopPropagation(); }

    let schema = [];
    if (schemaStr) {
        try {
            const decoded = safeAtob(schemaStr);
            schema = JSON.parse(decoded || '[]');
        } catch (e) {
            try { schema = JSON.parse(schemaStr || '[]'); } catch (e2) { schema = []; }
        }
    }

    let defaults = {};
    if (prefillB64) {
        try {
            defaults = JSON.parse(safeAtob(prefillB64) || '{}');
        } catch (e) {
            defaults = {};
        }
    }

    // Resolve any deferred context token coming from nested modal-grid-crud actions.
    const activeCrudModal = document.querySelector('.modal.show[data-context-b64]');
    if (activeCrudModal && activeCrudModal.dataset.contextB64) {
        let context = {};
        try {
            context = JSON.parse(safeAtob(activeCrudModal.dataset.contextB64) || '{}');
        } catch (e) {
            context = {};
        }

        Object.entries(defaults).forEach(([key, value]) => {
            if (typeof value !== 'string') return;
            defaults[key] = value.replace(/\{([^}]+)\}/g, (_, token) => String(context[token] ?? ''));
        });
    }

    openGenericModal(schema, actionUrl, 'POST', modalTitle, defaults);
}

export function openCrudGridModal(event, title = "Gestión", configB64 = "") {
    if (event) { event.preventDefault(); event.stopPropagation(); }

    let config = {};
    try {
        config = JSON.parse(safeAtob(configB64) || '{}');
    } catch (e) {
        try { config = JSON.parse(atob(configB64)); } catch (e2) { config = {}; }
    }

    const modalId = `modal-crud-${Math.random().toString(36).substr(2, 9)}`;
    const gridId = `grid-${Math.random().toString(36).substr(2, 9)}`;
    const toAttr = (value, fallback) => (value ?? fallback ?? '').replace(/'/g, '&#39;');
    const toJsonAttr = (value, fallback) => JSON.stringify(value ?? fallback ?? []).replace(/'/g, '&#39;');

    const gridHtml = `
        <div id="${gridId}"
            class="js-grid-visual"
            data-url="${toAttr(config.data_url, '')}"
            data-columns='${toJsonAttr(config.columns, [])}'
            data-actions='${toJsonAttr(config.actions, [])}'
            data-header-actions='${toJsonAttr(config.header_actions, [])}'
            data-schema='${toJsonAttr(config.schema, [])}'
            data-enable-filters="${config.enableFilters ? 'true' : 'false'}"
            data-filter-config='${toJsonAttr(config.filterConfig, {})}'
            data-polling=""
            data-row-key="${toAttr(config.row_key, '')}"
            data-polling-compare-fields='${toJsonAttr(config.polling_compare_fields, [])}'
            data-rows-b64="">
        </div>
    `;

    const modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-xl modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close" onclick="if(document.activeElement&&typeof document.activeElement.blur==='function'){document.activeElement.blur();}"></button>
                    </div>
                    <div class="modal-body">
                        ${gridHtml}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-light" data-bs-dismiss="modal" onclick="if(document.activeElement&&typeof document.activeElement.blur==='function'){document.activeElement.blur();}">Cerrar</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);

    const modalEl = document.getElementById(modalId);
    const modal = new bootstrap.Modal(modalEl);
    modalEl.dataset.contextB64 = safeBtoa(JSON.stringify(config.context || {}));
    modalEl.removeAttribute('inert');
    modal.show();

    modalEl.addEventListener('shown.bs.modal', () => {
        if (window.hydrateGrids) window.hydrateGrids();
    });

    modalEl.addEventListener('hide.bs.modal', () => {
        const activeEl = document.activeElement;
        if (activeEl && modalEl.contains(activeEl) && typeof activeEl.blur === 'function') {
            activeEl.blur();
        }
        modalEl.setAttribute('inert', '');
    });

    modalEl.addEventListener('hidden.bs.modal', () => {
        if (window.gridInstances && window.gridInstances[gridId]) {
            delete window.gridInstances[gridId];
        }
        modalEl.remove();
    });
}

/**
 * Global helpers for Repeater
 */
window.addRepeaterItem = async (name, source) => {
    const container = document.querySelector(`#repeater-${name} .repeater-list`);
    const itemHtml = `
        <div class="repeater-item d-flex gap-2 mb-2 align-items-center">
            <select class="form-select form-select-sm category-select" style="width: 140px;" data-source="${source}">
                <option value="">Category...</option>
            </select>
            <input type="text" class="form-control form-control-sm value-input" placeholder="Value...">
            <div class="form-check form-check-inline mb-0">
                <input class="form-check-input primary-radio" type="radio" name="${name}_primary">
            </div>
            <button type="button" class="btn btn-ghost-danger btn-icon btn-sm remove-item" onclick="this.closest('.repeater-item').remove()">
                <i class="ri-delete-bin-line"></i>
            </button>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', itemHtml);
    const newSelect = container.lastElementChild.querySelector('.category-select');
    await hydrateSelect(newSelect);
};

// Map to window for global access (backward compatibility)
window.submitModalForm = submitModalForm;
window.deleteItem = deleteItem;
window.handleEditAction = handleEditAction;
window.handleCreateAction = handleCreateAction;
window.openCrudGridModal = openCrudGridModal;
window.handleGenericAction = handleGenericAction;
window.hydrateSelect = hydrateSelect;
window.openGenericModal = openGenericModal;
