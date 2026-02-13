/**
 * Action Handlers Manager
 * Handles forms, deletes, modals, and generic SDUI actions.
 */

import { LinkModalForm, renderFormFromSchema } from '../../components/forms/ModalForm.js';
import { safeAtob, safeBtoa } from '../../utils/base64.js';

const API_BASE_URL = window.AppConfig.API_BASE_URL;

/**
 * Submits a modal form via AJAX.
 */
export async function submitModalForm(event, formId, actionUrl, method = 'POST') {
    if (event) event.preventDefault();

    const form = document.getElementById(formId);
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
    const modalHtml = LinkModalForm(modalId, title, formFields, url, method);

    const modalContainer = document.createElement('div');
    modalContainer.innerHTML = modalHtml;
    document.body.appendChild(modalContainer);

    const modalEl = document.getElementById(modalId);
    const modal = new bootstrap.Modal(modalEl);
    modal.show();

    modalEl.addEventListener('hidden.bs.modal', () => { modalContainer.remove(); });

    // Hydrate selects in the modal
    const selects = modalEl.querySelectorAll('select[data-source]');
    for (const select of selects) {
        await hydrateSelect(select);
    }
}

/**
 * Specialized Hydration for Selects
 */
export async function hydrateSelect(select) {
    const url = select.dataset.source;
    if (!url) return;
    const initialValue = select.dataset.value;

    try {
        const res = await fetch(`${API_BASE_URL}${url}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const items = await res.json();
        const placeholder = select.querySelector('option[value=""]') ? select.querySelector('option[value=""]').innerText : 'Select...';
        select.innerHTML = `<option value="">${placeholder}</option>`;

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
window.handleGenericAction = handleGenericAction;
window.hydrateSelect = hydrateSelect;
window.openGenericModal = openGenericModal;
