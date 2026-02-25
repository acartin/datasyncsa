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

const inferApiBaseUrl = () => {
    if (!runtimeBaseUrlOverride) return runtimeOrigin;
    try {
        const parsed = new URL(runtimeBaseUrlOverride, runtimeOrigin);
        if (parsed.hostname === window.location.hostname && !parsed.port && window.location.port) {
            localStorage.removeItem('admin_api_base_url');
            return runtimeOrigin;
        }
        return parsed.origin;
    } catch (_error) {
        localStorage.removeItem('admin_api_base_url');
        return runtimeOrigin;
    }
};
const apiBaseUrl = inferApiBaseUrl();

window.AppConfig = {
    API_BASE_URL: apiBaseUrl
};
