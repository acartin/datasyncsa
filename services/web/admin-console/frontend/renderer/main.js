/**
 * AI-First SDUI Renderer Engine (Modular Version)
 * Strictly follows 'visual_dictionary.json' and 'catalog_context.json'
 */

import { renderContent, renderComponent } from './engine/registry.js';
export { renderContent, renderComponent };
import { hydrateGrids } from './engine/hydration.js';
import './engine/actions.js'; // Attaches handlers to window
const RUNTIME_VERSION = (window.AppConfig && window.AppConfig.APP_VERSION) ? window.AppConfig.APP_VERSION : '1';

import { LinkAppShell } from '../components/layout/AppShell.js';
import { LinkSidebar } from '../components/layout/Sidebar.js';
import { LinkNavbar } from '../components/layout/Navbar.js';
import { LinkProjectBanner } from '../components/layout/ProjectBanner.js';

const API_BASE_URL = window.AppConfig.API_BASE_URL;
const RENDERER_VERSION = RUNTIME_VERSION;
console.log(`[Renderer] v${RENDERER_VERSION} Modular Initializing... (REGISTRY FIX)`);

window.appState = { currentPath: null };
window.navigateTo = navigateTo; // Expose for inline clicks
window.hydrateGrids = hydrateGrids;

async function init() {
    const appRoot = document.getElementById('app-root');
    try {
        const token = localStorage.getItem('access_token');
        const headers = {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        // Timeout Promise
        const timeout = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Connection timed out. Backend is unresponsive.')), 5000)
        );

        // Race fetch against timeout
        const requestAppInit = (url) => fetch(url, { headers, cache: 'no-store' });
        let response = await Promise.race([
            requestAppInit(`${API_BASE_URL}/app-init`),
            timeout
        ]);

        // Defensive retry to avoid intermittent stale/unauthorized responses on hard reload.
        if (response.status === 401 && token) {
            response = await Promise.race([
                requestAppInit(`${API_BASE_URL}/app-init?_ts=${Date.now()}`),
                timeout
            ]);
        }

        if (response.status === 401) {
            window.location.href = '/login.html';
            return;
        }
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const appData = await response.json();

        // Normal Boot Process...
        if (appData.layout === 'dashboard-shell') {
            if (appData.content) appData.contentHtml = renderContent(appData.content);
            const shellHtml = LinkAppShell(appData);

            const existingWrapper = document.getElementById('layout-wrapper');
            if (existingWrapper) existingWrapper.outerHTML = shellHtml;
            else document.body.insertAdjacentHTML('afterbegin', shellHtml);

            setupThemeSwitcher();
            updateHeaderProfile();
            setupNavigation();

            const currentPath = `${window.location.pathname}${window.location.search || ''}`;
            if (currentPath && currentPath !== '/' && currentPath !== '/index.html') {
                navigateTo(currentPath);
            } else {
                hydrateGrids();
            }
        }
    } catch (error) {
        console.error('Render Error:', error);
        // EMERGENCY MODE UI
        document.body.innerHTML = `
            <div class="ac-emergency-screen">
                <h1 class="ac-emergency-title">⚠️ EMERGENCY MODE</h1>
                <p>The Application failed to initialize.</p>
                <div class="ac-emergency-box">
                    <textarea readonly class="ac-emergency-textarea">${(error.stack || error.message || JSON.stringify(error) || "Unknown Error")}</textarea>
                    <button type="button" class="ac-emergency-copy-btn" onclick="navigator.clipboard.writeText(this.previousElementSibling.value); this.innerText='COPIED!'">COPY ERROR TO CLIPBOARD</button>
                </div>
                <button class="ac-emergency-retry-btn" onclick="window.location.reload()">
                    Retry Connection
                </button>
            </div>
        `;
    }
}

export async function navigateTo(href, pushState = true) {
    if (!href || href === '#' || href.startsWith('#')) return;

    // PERSISTENCE LOGIC START
    // If we are leaving a grid view (e.g. /leads/me) to go to a detail view, save the grid URL.
    const isDetailView = /\/leads(?:_v2)?\/[0-9a-fA-F-]{36}/.test(href);
    if (isDetailView && window.location.pathname !== href) {
        localStorage.setItem('last_active_grid_url', window.location.pathname);
    }
    // PERSISTENCE LOGIC END
    // PERSISTENCE LOGIC END

    window.appState.currentPath = href;
    const pageRoot = document.getElementById('page-root');
    if (!pageRoot) return;

    pageRoot.innerHTML = `<div class="text-center mt-5"><div class="spinner-border text-primary" role="status"></div></div>`;

    try {
        const token = localStorage.getItem('access_token');
        const headers = {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const toggleTrailingSlash = (path) => {
            const [pathname, query = ''] = String(path).split('?');
            if (!pathname || pathname === '/') return path;
            const toggled = pathname.endsWith('/') ? pathname.slice(0, -1) : `${pathname}/`;
            return query ? `${toggled}?${query}` : toggled;
        };

        let resolvedHref = href;
        let response = await fetch(`${API_BASE_URL}${resolvedHref}`, { headers, cache: 'no-store' });
        if (!response.ok) throw new Error(`View not found (${response.status})`);

        let contentType = response.headers.get('content-type') || '';
        if (!contentType.toLowerCase().includes('application/json')) {
            const altHref = toggleTrailingSlash(resolvedHref);
            if (altHref !== resolvedHref) {
                const altResponse = await fetch(`${API_BASE_URL}${altHref}`, { headers, cache: 'no-store' });
                const altContentType = altResponse.headers.get('content-type') || '';
                if (altResponse.ok && altContentType.toLowerCase().includes('application/json')) {
                    resolvedHref = altHref;
                    response = altResponse;
                    contentType = altContentType;
                }
            }
        }

        if (!contentType.toLowerCase().includes('application/json')) {
            throw new Error(`Invalid view payload (expected JSON). status=${response.status} content-type=${contentType} url=${response.url}`);
        }

        const viewData = await response.json();
        if (viewData.debug_data) {
            console.log("[Lead Detail Data]:", viewData.debug_data);
        }
        if (viewData.layout === 'dashboard-project-overview') {
            const bannerHtml = LinkProjectBanner(viewData);
            let tabsContentHtml = '';
            if (viewData.tabs) {
                tabsContentHtml = viewData.tabs.map(tab => {
                    const activeClass = tab.active ? 'show active' : '';
                    return `<div class="tab-pane fade ${activeClass}" id="${tab.id}" role="tabpanel">${renderContent(tab.components)}</div>`;
                }).join('');
            } else {
                tabsContentHtml = `<div class="tab-pane fade show active" id="project-overview" role="tabpanel">${renderContent(viewData.components)}</div>`;
            }
            pageRoot.innerHTML = `${bannerHtml}<div class="tab-content text-muted mt-3">${tabsContentHtml}</div>`;
        } else if (viewData.components) {
            pageRoot.innerHTML = renderContent(viewData.components);
        }

        hydrateGrids();

        if (pushState) history.pushState(null, '', resolvedHref);
        document.body.classList.remove('vertical-sidebar-enable');
    } catch (error) {
        console.error('Navigation Error:', error);
        pageRoot.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
    }
}

function setupThemeSwitcher() {
    const btn = document.querySelector('.light-dark-mode');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const html = document.documentElement;
        const currentMode = html.getAttribute('data-bs-theme') || 'light';
        const newMode = currentMode === 'light' ? 'dark' : 'light';
        html.setAttribute('data-bs-theme', newMode);
        html.setAttribute('data-layout-mode', newMode);
        localStorage.setItem('theme-mode', newMode);
    });
    const savedMode = localStorage.getItem('theme-mode');
    if (savedMode) {
        document.documentElement.setAttribute('data-bs-theme', savedMode);
        document.documentElement.setAttribute('data-layout-mode', savedMode);
    }
}

function setupNavigation() {
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a.nav-link') || e.target.closest('.js-navigate');
        if (!link) return;
        const href = link.getAttribute('href') || link.dataset.url;
        if (!href || href === '#' || href.startsWith('#')) return;
        e.preventDefault();
        navigateTo(href, true);
    });
    window.addEventListener('popstate', () => {
        const path = window.location.pathname;
        if (path) navigateTo(path, false);
    });
}

function updateHeaderProfile() {
    try {
        const profileStr = localStorage.getItem('user_profile');
        if (!profileStr) return;
        const profile = JSON.parse(profileStr);
        const nameEl = document.getElementById('header-user-name');
        if (nameEl && profile.name) nameEl.textContent = profile.name;
        const tenantEl = document.getElementById('header-tenant-name');
        if (tenantEl) {
            if (profile.is_superuser) tenantEl.textContent = 'Global Administrator';
            else if (profile.tenants?.length > 0) {
                const tenant = profile.tenants[0];
                const roleLabel = tenant.role?.name || 'User';
                tenantEl.textContent = tenant.client?.name ? `${roleLabel} - ${tenant.client.name}` : roleLabel;
            }
        }
    } catch (e) {
        console.warn('Profile update fail:', e);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
window.navigateTo = navigateTo; // For global access if needed
