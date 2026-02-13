import { LinkSidebar } from './Sidebar.js';
import { LinkNavbar } from './Navbar.js';

export function LinkAppShell(data) {
    const sidebarHtml = LinkSidebar(data.sidebar);
    const navbarHtml = LinkNavbar(data.navbar);
    // Decoupled: Expect pre-rendered HTML
    const contentHtml = data.contentHtml || '';

    // Official Velzon Structure
    return `
        <div id="layout-wrapper">
            
            ${navbarHtml}

            ${sidebarHtml}

            <!-- Vertical Overlay-->
            <div class="vertical-overlay"></div>

            <div class="main-content">
                <div class="page-content">
                    <div class="container-fluid" id="page-root">
                        ${contentHtml}
                    </div>
                </div>
                
                <footer class="footer">
                    <div class="container-fluid">
                        <div class="row">
                            <div class="col-sm-6">
                                ${2026} © AI-Realtor.
                            </div>
                            <div class="col-sm-6">
                                <div class="text-sm-end d-none d-sm-block">
                                    Lead Manager
                                </div>
                            </div>
                        </div>
                    </div>
                </footer>
            </div>
        </div>
    `;
}
