/**
 * Hydration Manager
 * Handles the initialization of interactive components (Grids, etc.)
 */

import { safeAtob, safeBtoa } from '../../utils/base64.js';
import { formatters } from './formatters.js';
import { LeadsGrid } from './LeadsGrid.js'; // Import new engine (Clean V2)
import { GridFilters } from './GridFilters.js'; // Import GridFilters module
import { TableGrid } from './TableGrid.js';

const API_BASE_URL = window.AppConfig.API_BASE_URL;




export async function hydrateGrids() {
    // 1. Standard Grid.js Instances
    const grids = document.querySelectorAll('.js-grid-visual');
    if (grids.length > 0) {
        // ... (Existing Grid.js logic) ...
        _hydrateStandardGrids(grids);
    }

    // 2. Custom Grid Instances (Beta)
    const customGrids = document.querySelectorAll('[data-type="custom-leads-grid"]');
    customGrids.forEach(container => {
        if (container.dataset.initialized) return;
        container.dataset.initialized = "true";

        // console.log("Hydrating LeadsGrid:", container.id);

        const config = {
            grid_id: container.dataset.gridId || 'default',
            data_url: container.dataset.url,
            columns: JSON.parse(container.dataset.columns || '[]'),
            actions: JSON.parse(container.dataset.actions || '[]'),
            header_actions: JSON.parse(container.dataset.headerActions || '[]'),
            enableFilters: container.dataset.enableFilters === 'true',
            filterConfig: JSON.parse(container.dataset.filterConfig || '{}')
        };

        // console.log('[Hydration] Grid config:', config);


        // Initialize Engine
        if (!window.gridInstances) window.gridInstances = {};
        window.gridInstances[container.id] = new LeadsGrid(container, config);
    });
}

// Renamed internal helper to keep code clean (Refactoring existing hydrateGrids logic)

async function _hydrateStandardGrids(grids) {
    // Initialize registry to prevent "undefined" errors
    window.gridInstances = window.gridInstances || {};

    grids.forEach(async (container) => {
        if (container.dataset.initialized) return;

        // Use existing ID or generate one
        const gridId = container.id || `grid-${Math.random().toString(36).substr(2, 9)}`;
        container.id = gridId;

        // console.log(`[Hydration] Standard Grid detected: ${gridId}`);

        // Instantiate encapsulated engine
        const instance = new TableGrid(container, {
            grid_id: gridId,
            data_url: container.dataset.url,
            // StandardGrid expected these in the constructor, but TableGrid/GridBase wants them in config
            columns: JSON.parse(container.dataset.columns || '[]'),
            actions: JSON.parse(container.dataset.actions || '[]'),
            header_actions: JSON.parse(container.dataset.headerActions || '[]'),
            enableFilters: container.dataset.enableFilters === 'true',
            filterConfig: JSON.parse(container.dataset.filterConfig || '{}'),
            form_schema: (() => {
                const s = container.dataset.schema;
                if (!s) return [];
                try { return JSON.parse(safeAtob(s)); }
                catch (e) { try { return JSON.parse(s); } catch (e2) { return []; } }
            })(),
            polling: container.dataset.polling,
            row_key: container.dataset.rowKey || '',
            polling_compare_fields: (() => {
                const raw = container.dataset.pollingCompareFields;
                if (!raw) return [];
                try { return JSON.parse(raw); } catch (e) { return []; }
            })()
        });
        window.gridInstances[gridId] = instance;
    });
}




export async function refreshGrids() {
    // console.log("[Hydration] Refreshing all active grids...");
    if (!window.gridInstances) return;

    Object.keys(window.gridInstances).forEach(id => {
        const grid = window.gridInstances[id];
        const el = document.getElementById(id);

        if (!el) {
            // Cleanup stale instance
            delete window.gridInstances[id];
            return;
        }

        if (grid && typeof grid.forceRender === 'function') {
            // Standard Unified Interface (GridBase)
            grid.forceRender();
        } else if (grid && typeof grid.refresh === 'function') {
            // Fallback
            grid.refresh();
        }
    });
}

window.refreshGrids = refreshGrids;

// Robust Copy Function (Works on HTTP/Non-Secure)
window.copyDebugInfo = function (id) {
    const el = document.getElementById(id);
    if (!el) return;
    const text = el.innerText;

    // Method 1: Modern API (Try first)
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => showFeedback(id)).catch(() => useFallback(text, id));
    } else {
        useFallback(text, id);
    }
};

function useFallback(text, id) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        const successful = document.execCommand('copy');
        if (successful) showFeedback(id);
        else console.error('Fallback copy command failed');
    } catch (err) {
        console.error('Fallback copy failed', err);
    }
    document.body.removeChild(textArea);
}

function showFeedback(id) {
    const parent = document.getElementById(id).parentElement;
    const btn = parent ? parent.querySelector('button') : null;
    if (btn) {
        const original = btn.innerText;
        btn.innerText = 'COPIED!';
        setTimeout(() => btn.innerText = original, 2000);
    }
}

