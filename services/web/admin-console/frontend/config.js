/**
 * Global App Configuration
 * This file should be loaded before any other script.
 * Supports runtime override via localStorage key `admin_api_port`.
 */
const runtimeProtocol = window.location.protocol || 'http:';
const runtimeHost = window.location.hostname;
const runtimePortOverride = localStorage.getItem('admin_api_port');
const runtimeWebPort = window.location.port;

// If running in local split-port mode (8085 UI), infer API at 8084.
const inferredApiPort = runtimeWebPort === '8085' ? '8084' : '';

// Default to same-origin, unless override/inferred API port is provided.
const runtimeOrigin = window.location.origin;
const resolvedApiPort = runtimePortOverride || inferredApiPort;
const apiBaseUrl = runtimePortOverride
    ? `${runtimeProtocol}//${runtimeHost}:${runtimePortOverride}`
    : resolvedApiPort
        ? `${runtimeProtocol}//${runtimeHost}:${resolvedApiPort}`
    : runtimeOrigin;

window.AppConfig = {
    API_BASE_URL: apiBaseUrl
};
