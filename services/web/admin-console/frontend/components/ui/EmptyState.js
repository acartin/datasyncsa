
export function LinkEmptyState(component) {
    const props = component.properties || {};
    const title = props.title || 'Próximamente';
    const message = props.message || 'Esta información se mostrará aquí.';
    const icon = props.icon || 'ri-information-line';

    return `
        <div class="p-5 text-center text-muted">
            <i class="${icon} display-4 mb-3 d-block text-secondary"></i>
            <h4>${title}</h4>
            <p>${message}</p>
        </div>
    `;
}
