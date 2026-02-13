
export function LinkBackLink(component) {
    const props = component.properties || {};
    const text = props.text || 'Volver';
    const fallbackUrl = props.fallback_url || '/dashboard';

    // The logic to return to the last active grid
    const onclickHandler = `
        const lastGrid = localStorage.getItem('last_active_grid_url') || '${fallbackUrl}'; 
        window.navigateTo(lastGrid);
    `;

    return `
        <a href="javascript:void(0)" 
           onclick="${onclickHandler.replace(/\n/g, '')}" 
           class="text-decoration-none text-muted mb-3 d-inline-block">
            <i class="ri-arrow-left-line me-1"></i> ${text}
        </a>
    `;
}
