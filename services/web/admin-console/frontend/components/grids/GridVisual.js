export function LinkGridVisual(component) {
    const props = component.properties || {};
    const filters = props.filters || [];

    return `
        <div class="card">
            <div class="card-body">
                <div id="${props.id || 'grid-' + Math.random().toString(36).substr(2, 9)}"
                    class="js-grid-visual"
                    data-url="${props.data_url || ''}"
                    data-url-template="${props.data_url_template || ''}"
                    data-columns='${JSON.stringify(props.columns || [])}'
                    data-actions='${JSON.stringify(props.actions || [])}'
                    data-header-actions='${JSON.stringify(props.header_actions || [])}'
                    data-schema='${JSON.stringify(props.schema || props.form_schema || [])}'
                    data-filters='${JSON.stringify(filters)}'
                    data-enable-filters="${props.enableFilters ? 'true' : 'false'}"
                    data-navigate-on-click="${props.navigate_on_click ? 'true' : 'false'}"
                    data-navigate-url="${props.navigate_url || ''}"
                    data-filter-config='${JSON.stringify(props.filterConfig || {})}'
                    data-polling="${props.polling || ''}"
                    data-row-key="${props.row_key || ''}"
                    data-auto-select-first-row="${props.auto_select_first_row ? 'true' : 'false'}"
                    data-master-grid-id="${props.master_grid_id || ''}"
                    data-master-row-field="${props.master_row_field || 'id'}"
                    data-master-url-token="${props.master_url_token || '{master_id}'}"
                    data-empty-until-master="${props.empty_until_master ? 'true' : 'false'}"
                    data-polling-compare-fields='${JSON.stringify(props.polling_compare_fields || [])}'
                    data-rows-b64="${props.rows_b64 || ''}">
                </div>
            </div>
        </div>
    `;
}
