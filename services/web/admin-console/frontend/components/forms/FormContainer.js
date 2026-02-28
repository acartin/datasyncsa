import { renderContent } from '../../renderer/engine/registry.js';

export function LinkFormContainer(component) {
    const props = component.properties || component;
    const formId = props.id || `form-${Math.random().toString(36).substr(2, 9)}`;
    const actionUrl = props.action_url || props.url || '';
    const method = props.method || 'POST';
    const schema = props.schema || [];

    // Simple field renderer (matches ModalForm logic but simplified)
    const fieldsHtml = schema.map(field => {
        let inputHtml = '';
        const fieldID = `${formId}-${field.name}`;

        if (field.type === 'select') {
            const options = (field.options || []).map(opt =>
                `<option value="${opt.value || opt}">${opt.label || opt}</option>`
            ).join('');
            inputHtml = `<select class="form-select" id="${fieldID}" name="${field.name}" ${field.required ? 'required' : ''}>${options}</select>`;
        } else if (field.type === 'textarea') {
            inputHtml = `<textarea class="form-control" id="${fieldID}" name="${field.name}" rows="3" ${field.required ? 'required' : ''}></textarea>`;
        } else if (field.type === 'color') {
            inputHtml = `<input type="color" class="form-control form-control-color w-100" id="${fieldID}" name="${field.name}" value="${field.value || ('#' + '000000')}" title="Choose your color">`;
        } else if (field.type === 'file') {
            inputHtml = `
                <input type="file" class="form-control" id="${fieldID}" name="${field.name}" accept="${field.accept || '*/*'}" 
                    onchange="validateFileSize(this, '${fieldID}-help')">
                <div id="${fieldID}-help" class="form-text text-muted">Max: 100MB</div>
            `;
        } else {
            inputHtml = `<input type="${field.type || 'text'}" class="form-control" id="${fieldID}" name="${field.name}" value="${field.value || ''}" ${field.required ? 'required' : ''}>`;
        }

        return `
            <div class="mb-3">
                <label for="${fieldID}" class="form-label">${field.label}</label>
                ${inputHtml}
            </div>
        `;
    }).join('');

    return `
        <div class="card">
            <div class="card-header align-items-center d-flex">
                <h4 class="card-title mb-0 flex-grow-1">${props.label || 'Formulario'}</h4>
            </div>
            <div class="card-body">
                <form id="${formId}" action="${actionUrl}" method="${method}" enctype="multipart/form-data" onsubmit="window.handleFormSubmit(event, '${formId}')">
                    ${fieldsHtml}
                    <div class="text-end">
                        <button type="submit" class="btn btn-primary">Guardar Cambios</button>
                    </div>
                </form>
            </div>
        </div>
    `;
}
