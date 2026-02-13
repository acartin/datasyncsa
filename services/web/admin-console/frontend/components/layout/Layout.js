import { renderComponent } from '../../renderer/engine/registry.js';

export function LinkRow(data) {
    const childrenHtml = (data.components || [])
        .map(c => renderComponent(c))
        .join('');

    return `
        <div class="row ${data.class_ || data.class || ''}">
            ${childrenHtml}
        </div>
    `;
}

export function LinkCol(data) {
    const childrenHtml = (data.components || [])
        .map(c => renderComponent(c))
        .join('');

    // If class_ is provided, use it directly (for col-auto, etc)
    // Otherwise, use size with col-xl-{size} col-lg-{size}
    let colClass = '';
    if (data.class_) {
        colClass = data.class_;
    } else {
        const size = data.size || 12;
        colClass = `col-xl-${size} col-lg-${size}`;
    }

    return `
        <div class="${colClass}">
            ${childrenHtml}
        </div>
    `;
}
