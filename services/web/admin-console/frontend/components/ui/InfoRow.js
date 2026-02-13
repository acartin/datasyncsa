
export function LinkInfoRow(component) {
    const props = component.properties || {};

    const label = props.label || 'Label';
    const value = props.value || '-';
    const icon = props.icon || 'ri-information-line';
    const color = props.color || 'primary';
    const marginBottom = props.last ? 'mb-0' : 'mb-3';

    return `
        <div class="d-flex align-items-center ${marginBottom}">
            <div class="avatar-sm flex-shrink-0 me-3">
                <div class="avatar-title bg-${color}-subtle text-${color} rounded-circle fs-3">
                    <i class="${icon}"></i>
                </div>
            </div>
            <div>
                <h5 class="fs-13 mb-0 text-muted">${label}</h5>
                <p class="fs-14 mb-0 fw-medium text-muted">${value}</p>
            </div>
        </div>
    `;
}
