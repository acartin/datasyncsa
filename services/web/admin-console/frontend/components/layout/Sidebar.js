export function LinkSidebar(data) {

    const menuItemsHtml = (data.items || [])
        .map(item => MenuItem(item))
        .join('');

    return `
        <div class="app-menu navbar-menu">
            <div class="navbar-brand-box">
                <a href="/" class="logo logo-dark">
                    <span class="logo-sm">
                        <img src="themes/images/logo-sm.png" alt="" height="22">
                    </span>
                    <span class="logo-lg">
                        <img src="themes/images/logo-light.png" alt="" height="17">
                    </span>
                </a>
                <button type="button" class="btn btn-sm p-0 fs-20 header-item float-end btn-vertical-sm-hover" id="vertical-hover">
                    <i class="ri-record-circle-line"></i>
                </button>
            </div>
            <div id="scrollbar">
                <div class="container-fluid">
                    <div id="two-column-menu"></div>
                    <ul class="navbar-nav" id="navbar-nav">
                        <li class="menu-title"><span data-key="t-menu">Menu</span></li>

                        ${menuItemsHtml}

                    </ul>
                </div>
            </div>
        </div>
    `;
}

function MenuItem(item) {
    const hasSubItems = item.subItems && item.subItems.length > 0;
    const itemID = item.id || Math.random().toString(36).substr(2, 9);

    if (hasSubItems) {
        const subItemsHtml = item.subItems.map(sub => `
            <li class="nav-item">
                <a href="${sub.link || '#'}" class="nav-link" data-key="t-${sub.id}">
                    ${sub.label}
                </a>
            </li>
        `).join('');

        return `
            <li class="nav-item">
                <a class="nav-link menu-link" href="#sidebar${itemID}" data-bs-toggle="collapse" role="button" aria-expanded="false" aria-controls="sidebar${itemID}">
                    ${item.icon ? `<i class="${item.icon}"></i>` : ''} 
                    <span data-key="t-${itemID}">${item.label}</span>
                </a>
                <div class="collapse menu-dropdown" id="sidebar${itemID}">
                    <ul class="nav nav-sm flex-column">
                        ${subItemsHtml}
                    </ul>
                </div>
            </li>
        `;
    } else {
        return `
            <li class="nav-item">
                <a class="nav-link menu-link" href="${item.link || '#'}">
                    ${item.icon ? `<i class="${item.icon}"></i>` : ''}
                    <span data-key="t-${itemID}">${item.label}</span>
                </a>
            </li>
        `;
    }
}
