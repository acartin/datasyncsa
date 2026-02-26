
export function LinkModalForm(id, title, formHtml, saveActionUrl, method = 'POST', dialogClass = '', dialogStyle = '') {
    const dialogClassAttr = dialogClass ? ` ${dialogClass}` : '';
    const dialogStyleAttr = dialogStyle ? ` style="${dialogStyle}"` : '';
    return `
    <div class="modal fade" id="${id}" tabindex="-1" aria-labelledby="${id}Label" aria-hidden="true">
        <div class="modal-dialog${dialogClassAttr}"${dialogStyleAttr}>
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="${id}Label">${title}</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close" onclick="if(document.activeElement&&typeof document.activeElement.blur==='function'){document.activeElement.blur();}"></button>
                </div>
                <div class="modal-body">
                    <form id="${id}-form" action="${saveActionUrl}" method="${method}" enctype="multipart/form-data" onsubmit="return false;">
                        ${formHtml}
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-light" data-bs-dismiss="modal" onclick="if(document.activeElement&&typeof document.activeElement.blur==='function'){document.activeElement.blur();}">Close</button>
                    <button type="button" class="btn btn-primary" onclick="window.submitModalForm(event, '${id}-form', '${saveActionUrl}', '${method}')">Save Changes</button>
                </div>
            </div>
        </div>
    </div>
    `;
}

const JSON_EDITOR_FIELD_NAMES = new Set(['extraction_schema_legacy']);

function toTextAreaValue(value) {
    let textValue = value;
    if (textValue && typeof textValue === 'object') {
        try {
            textValue = JSON.stringify(textValue, null, 2);
        } catch (e) {
            textValue = String(textValue);
        }
    } else if (textValue === null || textValue === undefined) {
        textValue = '';
    }
    return String(textValue);
}

function renderJsonEditorField(label, name, textValue, required, validation, attrs = '') {
    const readonlyAttr = validation.readonly ? 'readonly' : '';
    const rows = validation.rows || 16;
    const requiredAttr = required ? 'required' : '';
    const editorHostId = `${name}-json-host`;
    const fallbackId = `${name}-json-fallback`;

    return `
        <div class="mb-3 js-json-editor-group" data-json-field="${name}">
            <label for="${fallbackId}" class="form-label">${label}</label>
            <div class="d-flex align-items-center gap-2 mb-2">
                <button type="button" class="btn btn-light btn-sm js-json-format">Format</button>
                <button type="button" class="btn btn-light btn-sm js-json-compact">Compact</button>
                <span class="small text-muted js-json-status">Preparando editor JSON...</span>
            </div>
            <div id="${editorHostId}" class="js-json-editor-host border rounded" style="height: 360px;"></div>
            <textarea class="form-control d-none js-json-source" id="${name}" name="${name}" rows="${rows}"
                ${requiredAttr} ${attrs} ${readonlyAttr}>${textValue}</textarea>
            <textarea class="form-control d-none js-json-fallback mt-2" id="${fallbackId}" rows="${rows}"
                ${requiredAttr} ${attrs} ${readonlyAttr}>${textValue}</textarea>
            <div class="form-text">Tip: cambia a modo código en el menú del editor si quieres pegar JSON completo.</div>
        </div>
    `;
}

function setJsonStatus(group, message, isError = false) {
    const status = group.querySelector('.js-json-status');
    if (!status) return;
    status.textContent = message || '';
    status.classList.toggle('text-danger', Boolean(isError));
    status.classList.toggle('text-muted', !isError);
}

function syncTextJson(group) {
    const source = group.querySelector('.js-json-source');
    const fallback = group.querySelector('.js-json-fallback');
    const raw = String((fallback?.value ?? source?.value ?? '')).trim();
    const sourceName = source?.name || 'json';

    if (source && fallback) source.value = fallback.value;
    if (!raw) {
        setJsonStatus(group, 'JSON vacío (se guardará null).');
        return { ok: true };
    }

    try {
        JSON.parse(raw);
        setJsonStatus(group, 'JSON válido.');
        return { ok: true };
    } catch (error) {
        const detail = error?.message || 'estructura inválida';
        setJsonStatus(group, `JSON inválido: ${detail}`, true);
        return { ok: false, message: `JSON inválido en ${sourceName}: ${detail}` };
    }
}

function formatTextJson(group, compact = false) {
    const source = group.querySelector('.js-json-source');
    const fallback = group.querySelector('.js-json-fallback');
    if (!fallback) return;

    const raw = String(fallback.value || '').trim();
    if (!raw) {
        if (source) source.value = fallback.value;
        setJsonStatus(group, 'JSON vacío (sin cambios).');
        return;
    }

    try {
        const parsed = JSON.parse(raw);
        const formatted = compact ? JSON.stringify(parsed) : JSON.stringify(parsed, null, 2);
        fallback.value = formatted;
        if (source) source.value = formatted;
        setJsonStatus(group, 'JSON formateado.');
    } catch (error) {
        const detail = error?.message || 'estructura inválida';
        setJsonStatus(group, `JSON inválido: ${detail}`, true);
    }
}

function getEditorText(editor) {
    if (!editor) return '';
    if (typeof editor.getText === 'function') return editor.getText();
    if (typeof editor.get === 'function') return JSON.stringify(editor.get(), null, 2);
    return '';
}

function formatEditorJson(group, compact = false) {
    const editor = group._jsonEditor;
    const source = group.querySelector('.js-json-source');
    const fallback = group.querySelector('.js-json-fallback');
    if (!editor) {
        formatTextJson(group, compact);
        return;
    }

    try {
        const currentText = String(getEditorText(editor) || '').trim();
        if (!currentText) {
            editor.set({});
            const emptyValue = compact ? '{}' : JSON.stringify({}, null, 2);
            if (source) source.value = emptyValue;
            if (fallback) fallback.value = emptyValue;
            setJsonStatus(group, 'JSON inicializado.');
            return;
        }

        const parsed = JSON.parse(currentText);
        const formatted = compact ? JSON.stringify(parsed) : JSON.stringify(parsed, null, 2);
        if (typeof editor.setText === 'function') {
            editor.setText(formatted);
        } else {
            editor.set(parsed);
        }
        if (source) source.value = formatted;
        if (fallback) fallback.value = formatted;
        setJsonStatus(group, 'JSON formateado.');
    } catch (error) {
        const detail = error?.message || 'estructura inválida';
        setJsonStatus(group, `JSON inválido: ${detail}`, true);
    }
}

export function initJsonEditors(rootEl = document) {
    const groups = rootEl.querySelectorAll('.js-json-editor-group');
    groups.forEach((group) => {
        if (group.dataset.initialized === '1') return;

        const source = group.querySelector('.js-json-source');
        const fallback = group.querySelector('.js-json-fallback');
        const host = group.querySelector('.js-json-editor-host');
        const formatBtn = group.querySelector('.js-json-format');
        const compactBtn = group.querySelector('.js-json-compact');

        if (formatBtn) formatBtn.addEventListener('click', () => formatEditorJson(group, false));
        if (compactBtn) compactBtn.addEventListener('click', () => formatEditorJson(group, true));

        if (!window.JSONEditor || !host || !source || !fallback) {
            if (host) host.classList.add('d-none');
            if (fallback) {
                fallback.classList.remove('d-none');
                fallback.addEventListener('input', () => {
                    if (source) source.value = fallback.value;
                    syncTextJson(group);
                });
            }
            syncTextJson(group);
            setJsonStatus(group, 'Editor visual no disponible. Usando modo texto.');
            group.dataset.initialized = '1';
            return;
        }

        const initialText = String(source.value || '').trim();
        let parsedInitial = {};
        let hasValidInitial = false;
        if (initialText) {
            try {
                parsedInitial = JSON.parse(initialText);
                hasValidInitial = true;
            } catch (e) {
                hasValidInitial = false;
            }
        }

        if (!hasValidInitial && initialText) {
            host.classList.add('d-none');
            fallback.classList.remove('d-none');
            fallback.addEventListener('input', () => {
                source.value = fallback.value;
                syncTextJson(group);
            });
            setJsonStatus(group, 'JSON inicial inválido. Corrige en modo texto.', true);
            group.dataset.initialized = '1';
            return;
        }

        try {
            const editor = new window.JSONEditor(host, {
                mode: 'tree',
                modes: ['tree', 'code', 'view'],
                search: false,
                history: true,
                navigationBar: true,
                statusBar: true,
                mainMenuBar: true,
                onChangeText: (text) => {
                    const raw = String(text || '');
                    source.value = raw;
                    fallback.value = raw;
                    const trimmed = raw.trim();
                    if (!trimmed) {
                        setJsonStatus(group, 'JSON vacío (se guardará null).');
                        return;
                    }
                    try {
                        JSON.parse(trimmed);
                        setJsonStatus(group, 'JSON válido.');
                    } catch (error) {
                        const detail = error?.message || 'estructura inválida';
                        setJsonStatus(group, `JSON inválido: ${detail}`, true);
                    }
                },
            });

            editor.set(hasValidInitial ? parsedInitial : {});
            source.value = hasValidInitial ? JSON.stringify(parsedInitial, null, 2) : JSON.stringify({}, null, 2);
            fallback.value = source.value;
            fallback.classList.add('d-none');
            host.classList.remove('d-none');
            setJsonStatus(group, 'JSON válido.');
            group._jsonEditor = editor;
        } catch (error) {
            host.classList.add('d-none');
            fallback.classList.remove('d-none');
            fallback.addEventListener('input', () => {
                source.value = fallback.value;
                syncTextJson(group);
            });
            setJsonStatus(group, 'No se pudo iniciar el editor visual. Usando modo texto.', true);
        }

        group.dataset.initialized = '1';
    });
}

export function syncJsonEditors(formEl) {
    const groups = formEl.querySelectorAll('.js-json-editor-group');
    for (const group of groups) {
        const source = group.querySelector('.js-json-source');
        const fallback = group.querySelector('.js-json-fallback');
        let raw = '';

        if (group._jsonEditor) {
            try {
                raw = String(getEditorText(group._jsonEditor) || '');
            } catch (e) {
                raw = String(source?.value || '');
            }
        } else if (fallback && !fallback.classList.contains('d-none')) {
            raw = String(fallback.value || '');
        } else {
            raw = String(source?.value || '');
        }

        if (source) source.value = raw;
        if (fallback) fallback.value = raw;

        const trimmed = raw.trim();
        if (!trimmed) {
            setJsonStatus(group, 'JSON vacío (se guardará null).');
            continue;
        }

        try {
            JSON.parse(trimmed);
            setJsonStatus(group, 'JSON válido.');
        } catch (error) {
            const detail = error?.message || 'estructura inválida';
            const sourceName = source?.name || 'json';
            setJsonStatus(group, `JSON inválido: ${detail}`, true);
            return { ok: false, message: `JSON inválido en ${sourceName}: ${detail}` };
        }
    }
    return { ok: true };
}

export function destroyJsonEditors(rootEl = document) {
    const groups = rootEl.querySelectorAll('.js-json-editor-group');
    groups.forEach((group) => {
        if (group._jsonEditor && typeof group._jsonEditor.destroy === 'function') {
            group._jsonEditor.destroy();
        }
        delete group._jsonEditor;
        delete group.dataset.initialized;
    });
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
        const textValue = toTextAreaValue(value);
        const attrs = `${minLength} ${maxLength}`.trim();
        if (JSON_EDITOR_FIELD_NAMES.has(String(name || ''))) {
            return renderJsonEditorField(label, name, textValue, required, validation, attrs);
        }
        const readonlyAttr = validation.readonly ? 'readonly' : '';
        return `
            <div class="mb-3">
                <label for="${name}" class="form-label">${label}</label>
                <textarea class="form-control" id="${name}" name="${name}" rows="${validation.rows || 3}" 
                    ${isRequired} ${attrs} ${readonlyAttr}>${textValue}</textarea>
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
        const dependsOn = validation.depends_on || '';

        // If source is provided, we mark it for hydration
        const dataSourceAttr = sourceUrl ? `data-source="${sourceUrl}"` : '';
        const dataValueAttr = value ? `data-value="${value}"` : '';
        const dataDependsOnAttr = dependsOn ? `data-depends-on="${dependsOn}"` : '';

        return `
            <div class="mb-3">
                <label for="${name}" class="form-label">${label}</label>
                <select class="form-select" id="${name}" name="${name}" ${isRequired} ${dataSourceAttr} ${dataValueAttr} ${dataDependsOnAttr}>
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
            depends_on: field.depends_on,
            fields: field.fields,  // For group type
            layout: field.layout,  // For group type
            accept: field.accept,  // For file type
            readonly: field.readonly // For readonly fields
        };
        return renderInput(field.label, field.name, val, field.type, field.required, validation, data);
    }).join('');
}
