import { renderComponent } from '../../renderer/engine/registry.js';

export function LinkCard(data) {
    const title = data.title || '';
    const childrenHtml = (data.components || [])
        .map(c => renderComponent(c))
        .join('');

    return `
        <div class="card ${data.class || ''}">
            ${title ? `<div class="card-header"><h4 class="card-title mb-0">${title}</h4></div>` : ''}
            <div class="card-body">
                ${childrenHtml}
            </div>
        </div>
    `;
}
