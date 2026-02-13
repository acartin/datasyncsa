export function LinkCustomGridContainer(component) {
    const props = component.properties || {};
    return `
        <div id="grid-custom-${Math.random().toString(36).substr(2, 9)}"
             class="card h-100 shadow-sm"
             data-type="custom-leads-grid"
             data-grid-id="${props.grid_id || 'default'}"
             data-url="${props.data_url}"
             data-columns='${JSON.stringify(props.columns || [])}'
             data-actions='${JSON.stringify(props.actions || [])}'
             data-enable-filters="${props.enableFilters ? 'true' : 'false'}"
             data-filter-config='${JSON.stringify(props.filterConfig || {})}'>
             <div class="card-body p-3">
                <!-- Engine will hydrate here -->
                <div class="d-flex justify-content-center align-items-center" style="height: 200px;">
                    <span class="spinner-border text-primary me-2"></span> Initializing Beta Engine...
                </div>
             </div>
        </div>
    `;
}
