export function LinkButtonGroup(component) {
    const props = component.properties || {};
    const buttons = props.buttons || [];

    const buttonsHtml = buttons.map(btn => `
        <button class="btn ${btn.class || 'btn-primary'}">
            ${btn.icon ? `<i class="${btn.icon} me-1"></i>` : ''}${btn.label}
        </button>
    `).join('');

    return `
        <div class="btn-group gap-2" role="group">
            ${buttonsHtml}
        </div>
    `;
}
