/**
 * Global App Configuration
 * This file should be loaded before any other script.
 * Supports runtime override via localStorage key `admin_api_port`.
 */
const runtimePort = localStorage.getItem('admin_api_port') || '8084';
const runtimeProtocol = window.location.protocol || 'http:';

window.AppConfig = {
    API_BASE_URL: `${runtimeProtocol}//${window.location.hostname}:${runtimePort}`
};
