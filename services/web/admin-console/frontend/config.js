/**
 * Global App Configuration
 * This file should be loaded before any other script.
 * Supports runtime override via localStorage key `admin_api_base_url`.
 */
const runtimeOrigin = window.location.origin;
const runtimeBaseUrlOverride = localStorage.getItem('admin_api_base_url');
const legacyPortOverride = localStorage.getItem('admin_api_port');

// Cleanup legacy override to avoid stale split-port behavior via cached config.
if (legacyPortOverride) {
    localStorage.removeItem('admin_api_port');
}

// Default to same-origin so web Nginx proxies API routes without CORS.
const apiBaseUrl = runtimeBaseUrlOverride || runtimeOrigin;

window.AppConfig = {
    API_BASE_URL: apiBaseUrl
};
