
export function LinkModalForm(id, title, formHtml, saveActionUrl, method = 'POST') {
    return `
    <div class="modal fade" id="${id}" tabindex="-1" aria-labelledby="${id}Label" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="${id}Label">${title}</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <form id="${id}-form" action="${saveActionUrl}" method="${method}" enctype="multipart/form-data" onsubmit="return false;">
                        ${formHtml}
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-light" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-primary" onclick="window.submitModalForm(event, '${id}-form', '${saveActionUrl}', '${method}')">Save Changes</button>
                </div>
            </div>
        </div>
    </div>
    `;
}

// Helper to render a single input
export function renderInput(label, name, value = '', type = 'text', required = false, validation = {}, data = {}) {
    const isRequired = required ? 'required' : '';
    const minLength = validation.min_length ? `minlength="${validation.min_length}"` : '';
    const maxLength = validation.max_length ? `maxlength="${validation.max_length}"` : '';
    const pattern = validation.pattern ? `pattern="${validation.pattern}"` : '';

    // Group Field (for horizontal layouts)
    if (type === 'group') {
        const layout = validation.layout || 'vertical';
        const fields = validation.fields || [];
        const groupLabel = label || '';

        const fieldsHtml = fields.map(field => {
            // Get value from data object for each nested field
            let fieldValue = '';
            if (data[field.name] !== undefined && data[field.name] !== null) {
                fieldValue = data[field.name];
            } else if (field.value !== undefined) {
                fieldValue = field.value;
            }
            return renderInput(field.label, field.name, fieldValue, field.type || 'text', field.required || false, field, data);
        }).join('');

        if (layout === 'horizontal') {
            return `
                <div class="mb-3">
                    ${groupLabel ? `<label class="form-label">${groupLabel}</label>` : ''}
                    <div class="d-flex gap-3">
                        ${fieldsHtml}
                    </div>
                </div>
            `;
        }

        return `<div class="mb-3">${groupLabel ? `<label class="form-label">${groupLabel}</label>` : ''}${fieldsHtml}</div>`;
    }

    // Hidden Input Optimization
    if (type === 'hidden') {
        return `<input type="hidden" id="${name}" name="${name}" value="${value}">`;
    }

    if (type === 'textarea') {
        const readonlyAttr = validation.readonly ? 'readonly' : '';
        return `
            <div class="mb-3">
                <label for="${name}" class="form-label">${label}</label>
                <textarea class="form-control" id="${name}" name="${name}" rows="${validation.rows || 3}" 
                    ${isRequired} ${minLength} ${maxLength} ${readonlyAttr}>${value}</textarea>
            </div>
        `;
    }

    if (type === 'switch' || type === 'checkbox') {
        const isChecked = (value === true || value === 'true' || value === '1');
        const checkedStr = isChecked ? 'checked' : '';
        const roleSwitch = type === 'switch' ? 'role="switch"' : '';
        // Dynamic Color: Success (green) if checked, Secondary (gray) if unchecked
        const colorClass = isChecked ? 'form-switch-success' : 'form-switch-secondary';

        // Toggle Logic script: switches between success and secondary
        const toggleScript = `this.closest('.form-check').classList.remove('form-switch-success', 'form-switch-secondary'); this.closest('.form-check').classList.add(this.checked ? 'form-switch-success' : 'form-switch-secondary');`;

        return `
            <div class="mb-3 form-check form-switch ${colorClass}">
                <input class="form-check-input" type="checkbox" ${roleSwitch} id="${name}" name="${name}" ${checkedStr} ${isRequired} onchange="${toggleScript}">
                <label class="form-check-label" for="${name}">${label}</label>
            </div>
        `;
    }

    if (type === 'select') {
        const sourceUrl = validation.source || '';
        const optionsHtml = (validation.options || []).map(opt => `<option value="${opt.value}" ${opt.value == value ? 'selected' : ''}>${opt.label}</option>`).join('');

        // If source is provided, we mark it for hydration
        const dataSourceAttr = sourceUrl ? `data-source="${sourceUrl}"` : '';
        const dataValueAttr = value ? `data-value="${value}"` : '';

        return `
            <div class="mb-3">
                <label for="${name}" class="form-label">${label}</label>
                <select class="form-select" id="${name}" name="${name}" ${isRequired} ${dataSourceAttr} ${dataValueAttr}>
                    <option value="">Select...</option>
                    ${optionsHtml}
                </select>
            </div>
        `;
    }

    if (type === 'repeater') {
        const sourceUrl = validation.source || '';
        const items = Array.isArray(value) ? value : [];
        const itemsHtml = items.map((item, index) => `
            <div class="repeater-item d-flex gap-2 mb-2 align-items-center" data-index="${index}">
                <select class="form-select form-select-sm category-select" style="width: 140px;" data-source="${sourceUrl}" data-value="${item.category_id || ''}">
                    <option value="">Category...</option>
                </select>
                <input type="text" class="form-control form-control-sm value-input" placeholder="Value..." value="${item.value || ''}">
                <div class="form-check form-check-inline mb-0">
                    <input class="form-check-input primary-radio" type="radio" name="${name}_primary" ${item.is_primary ? 'checked' : ''} title="Set as Primary">
                </div>
                <button type="button" class="btn btn-ghost-danger btn-icon btn-sm remove-item" onclick="this.closest('.repeater-item').remove()">
                    <i class="ri-delete-bin-line"></i>
                </button>
            </div>
        `).join('');

        return `
            <div class="mb-3 repeater-container" id="repeater-${name}" data-name="${name}">
                <label class="form-label d-flex justify-content-between align-items-center">
                    ${label}
                    <button type="button" class="btn btn-soft-primary btn-sm add-item" onclick="window.addRepeaterItem('${name}', '${sourceUrl}')">
                        <i class="ri-add-line align-bottom"></i> Add
                    </button>
                </label>
                <div class="repeater-list">
                    ${itemsHtml}
                </div>
                <input type="hidden" name="${name}" id="input-${name}">
            </div>
            <script>
                // Self-contained logic for adding items if not already globally defined
                if (!window.addRepeaterItem) {
                    window.addRepeaterItem = (name, source) => {
                        const container = document.querySelector(\`#repeater-\${name} .repeater-list\`);
                        const itemHtml = \`
                            <div class="repeater-item d-flex gap-2 mb-2 align-items-center">
                                <select class="form-select form-select-sm category-select" style="width: 140px;" data-source="\${source}">
                                    <option value="">Category...</option>
                                </select>
                                <input type="text" class="form-control form-control-sm value-input" placeholder="Value...">
                                <div class="form-check form-check-inline mb-0">
                                    <input class="form-check-input primary-radio" type="radio" name="\${name}_primary">
                                </div>
                                <button type="button" class="btn btn-ghost-danger btn-icon btn-sm remove-item" onclick="this.closest('.repeater-item').remove()">
                                    <i class="ri-delete-bin-line"></i>
                                </button>
                            </div>
                        \`;
                        container.insertAdjacentHTML('beforeend', itemHtml);
                        // Hydrate the newly added select
                        const newSelect = container.lastElementChild.querySelector('.category-select');
                        if (window.hydrateSelect) window.hydrateSelect(newSelect);
                    };
                }
            </script>
        `;
    }

    if (type === 'file') {
        const helpId = `help-${name}`;
        // Extract filename from path if value exists (e.g., /path/to/file.jpg -> file.jpg)
        const currentFileName = value ? value.split('/').pop() : null;
        const currentFileInfo = currentFileName
            ? `<div class="text-muted small mb-1"><i class="ri-file-line"></i> Actual: <strong>${currentFileName}</strong></div>`
            : '';

        return `
            <div class="mb-3">
                <label for="${name}" class="form-label">${label}</label>
                ${currentFileInfo}
                <input type="file" class="form-control" id="${name}" name="${name}" 
                    accept="${validation.accept || 'image/*'}" 
                    ${isRequired} 
                    onchange="if(window.validateFileSize) window.validateFileSize(this, '${helpId}')">
                <div id="${helpId}" class="form-text mt-1">Max size: 100MB${currentFileName ? ' (dejar vacío para mantener el actual)' : ''}</div>
            </div>
        `;
    }

    const readonlyAttr = validation.readonly ? 'readonly' : '';
    return `
        <div class="mb-3">
            <label for="${name}" class="form-label">${label}</label>
            <input type="${type}" class="form-control ${type === 'color' ? 'form-control-color' : ''}" 
                id="${name}" name="${name}" value="${value}" 
                style="${type === 'color' ? 'width: 50px; height: 50px; padding: 2px; aspect-ratio: 1/1;' : ''}"
                ${isRequired} ${minLength} ${maxLength} ${pattern} ${readonlyAttr}>
        </div>
    `;
}

// NEW: Generic Form Renderer
export function renderFormFromSchema(schema, data = {}) {
    if (!Array.isArray(schema)) return '';
    return schema.map(field => {
        // Prioritize data[name] (edit mode), then field.value (schema default), then empty
        let val = '';
        if (data[field.name] !== undefined && data[field.name] !== null) {
            val = data[field.name];
        } else if (field.value !== undefined) {
            val = field.value;
        }

        // Pass validation rules if present in field definition
        const validation = {
            min_length: field.min_length,
            max_length: field.max_length,
            pattern: field.pattern,
            rows: field.rows,
            source: field.source,
            options: field.options,
            fields: field.fields,  // For group type
            layout: field.layout,  // For group type
            accept: field.accept,  // For file type
            readonly: field.readonly // For readonly fields
        };
        return renderInput(field.label, field.name, val, field.type, field.required, validation, data);
    }).join('');
}
