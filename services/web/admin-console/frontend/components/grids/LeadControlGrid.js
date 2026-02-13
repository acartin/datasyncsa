import { safeBtoa } from '../../utils/base64.js';

const API_BASE_URL = window.AppConfig.API_BASE_URL;

export function LinkLeadControlGrid(component) {
    const props = component.properties || {};
    const columns = props.columns || [];
    const gridId = `grid-control-${Math.random().toString(36).substr(2, 9)}`;
    const dataUrl = props.data_url;

    // Serialize data for hydration
    const columnsJson = JSON.stringify(props.columns || []);
    const actionsJson = JSON.stringify(props.actions || []);
    const filtersJson = JSON.stringify(props.filters || []);
    const rowsJson = JSON.stringify(component.rows || props.rows || []);
    const rowsB64 = safeBtoa(rowsJson);
    const label = component.label || component.title || 'Panel de Control de Leads';

    return `
        <div class="card border-0 shadow-none mb-0">
            <div class="card-header align-items-center d-flex bg-light-subtle py-3">
                <h4 class="card-title mb-0 flex-grow-1 fs-16 font-primary fw-semibold">${label}</h4>
                <div class="flex-shrink-0">
                    ${(props.header_actions || []).map(btn => renderHeaderAction(btn)).join('')}
                </div>
            </div>
            <div class="card-body p-0">
                <div class="js-grid-leads-control-parent">
                    <div id="${gridId}" 
                         class="js-grid-leads-control"
                         data-url="${dataUrl}"
                         data-columns='${columnsJson.replace(/'/g, "&apos;")}'
                         data-actions='${actionsJson.replace(/'/g, "&apos;")}'
                         data-filters='${filtersJson.replace(/'/g, "&apos;")}'
                         data-rows-b64="${rowsB64}"
                         >
                         <div class="text-center p-5">
                            <div class="spinner-border text-primary" role="status">
                                <span class="sr-only">Cargando Panel...</span>
                            </div>
                         </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderHeaderAction(btn) {
    return `
        <button type="button" class="btn btn-${btn.color || 'primary'} btn-sm shadow-none">
            <i class="${btn.icon} fs-14 align-middle me-1"></i> ${btn.label}
        </button>
    `;
}
