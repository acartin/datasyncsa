import { renderContent } from '../../renderer/engine/registry.js';

export function LinkTabs(data) {
    const tabsId = `tabs-${Math.random().toString(36).substr(2, 9)}`;

    // 1. Build Nav Tabs (Header)
    const navItems = data.items.map((item, index) => {
        const isActive = item.active || index === 0 ? 'active' : '';
        const iconHtml = item.icon ? `<i class="${item.icon} me-1 align-bottom"></i>` : '';

        return `
            <li class="nav-item">
                <a class="nav-link ${isActive}" data-bs-toggle="tab" href="#${tabsId}-${item.id}" role="tab">
                    ${iconHtml} ${item.label}
                </a>
            </li>
        `;
    }).join('');

    // 2. Build Tab Panes (Content)
    const tabPanes = data.items.map((item, index) => {
        const isActive = item.active || index === 0 ? 'active show' : '';
        // Render recursive content
        const contentHtml = renderContent(item.content);

        return `
            <div class="tab-pane ${isActive}" id="${tabsId}-${item.id}" role="tabpanel">
                <div class="d-flex mb-4">
                    <div class="flex-grow-1 p-3">
                         ${contentHtml}
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // 3. Assemble
    return `
        <div class="col-12">
            <div class="card">
                <div class="card-header">
                    <ul class="nav nav-tabs-custom card-header-tabs border-bottom-0" role="tablist">
                        ${navItems}
                    </ul>
                </div>
                <div class="card-body p-4">
                    <div class="tab-content">
                        ${tabPanes}
                    </div>
                </div>
            </div>
        </div>
    `;
}
