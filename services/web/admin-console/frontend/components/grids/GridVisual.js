export function LinkGridVisual(component) {
    const props = component.properties || {};
    const filters = props.filters || [];

    return `
        <div class="card">
            <div class="card-body">
                <div id="${props.id || 'grid-' + Math.random().toString(36).substr(2, 9)}"
                    class="js-grid-visual"
                    data-url="${props.data_url || ''}"
                    data-columns='${JSON.stringify(props.columns || [])}'
                    data-actions='${JSON.stringify(props.actions || [])}'
                    data-header-actions='${JSON.stringify(props.header_actions || [])}'
                    data-schema='${JSON.stringify(props.schema || props.form_schema || [])}'
                    data-filters='${JSON.stringify(filters)}'
                    data-enable-filters="${props.enableFilters ? 'true' : 'false'}"
                    data-filter-config='${JSON.stringify(props.filterConfig || {})}'
                    data-polling="${props.polling || ''}"
                    data-rows-b64="${props.rows_b64 || ''}">
                </div>
            </div>
        </div>
    `;
}
