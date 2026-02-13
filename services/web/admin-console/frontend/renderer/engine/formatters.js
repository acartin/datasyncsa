/**
 * Custom Column Formatters
 * Contains the visual logic for specific column types (Pills, Gauges, Badges).
 * Used by hydration.js to keep the core engine generic.
 */

// Helper to find the row ID column index safely
const getRowId = (row, gridColumns) => {
    const idColIndex = gridColumns.findIndex(c => c.id === 'id');
    return row.cells[idColIndex].data;
};

export const formatters = {
    /**
     * Renders a "Thermal Pill" for scoring columns.
     * Displays a colored badge with a label and links to the lead.
     */
    scoringPillar: (cell, row, gridColumns) => {
        const score = (typeof cell === 'object') ? (cell.score || 0) : (parseInt(cell) || 0);
        const label = (typeof cell === 'object') ? (cell.label || '-') : '-';
        const colorClass = (typeof cell === 'object') ? (cell.color || 'thermal-none') : 'thermal-none';
        const rowId = getRowId(row, gridColumns);

        return `
            <div class="text-center" title="Score: ${score}">
                <a href="javascript:void(0)" onclick="window.navigateTo('/dashboard/leads/${rowId}')" class="thermal-pill ${colorClass}">${label}</a>
            </div>
        `;
    },

    /**
     * Renders a circular Gauge with the lead's identity (Name + Score).
     * Visualizes the score with a colored stroke.
     */
    gaugeIdentity: (cell, row, gridColumns) => {
        const score = (typeof cell === 'object') ? (cell.score || 0) : (parseInt(cell) || 0);
        const name = (typeof cell === 'object') ? (cell.name || '') : '';
        const rowId = getRowId(row, gridColumns);

        let color = '#475569';
        if (score >= 90) color = '#f06548'; // Danger
        else if (score >= 70) color = '#f7b84b'; // Warning
        else if (score >= 50) color = '#4b38b3'; // Primary
        else if (score >= 20) color = '#0ab39c'; // Success

        const r = 14;
        const c = 2 * Math.PI * r;
        const offset = c - (score / 100) * c;

        return `
            <a href="javascript:void(0)" onclick="window.navigateTo('/dashboard/leads/${rowId}')" class="d-flex align-items-center text-decoration-none shadow-none">
                <div class="me-2 position-relative" style="width: 32px; height: 32px; cursor: pointer;">
                    <svg width="32" height="32" viewBox="0 0 32 32">
                        <circle cx="16" cy="16" r="${r}" fill="none" stroke="currentColor" stroke-width="2.5" style="opacity: 0.1"></circle>
                        <circle cx="16" cy="16" r="${r}" fill="none" stroke="${color}" stroke-width="2.5" 
                            stroke-dasharray="${c}" stroke-dashoffset="${offset}" 
                            stroke-linecap="round" transform="rotate(-90 16 16)"></circle>
                        <text x="50%" y="50%" text-anchor="middle" dy=".35em" font-size="10.5" font-weight="700" fill="currentColor">${score}</text>
                    </svg>
                </div>
                <div><h6 class="mb-0 fs-13 fw-medium text-body text-truncate" style="max-width: 180px;">${name}</h6></div>
            </a>
        `;
    },

    /**
     * Renders a Bootstrap Badge.
     * Supports mapping values to specific colors.
     */
    badge: (cell, col) => {
        const label = (typeof cell === 'object') ? (cell.label || cell.name || JSON.stringify(cell)) : cell;
        const color = (typeof cell === 'object' && cell.color) ? cell.color : (col.color || 'primary');
        const mapKey = String(label);
        const badgeColor = (col.badge_map && col.badge_map[mapKey]) ? col.badge_map[mapKey] : color;
        const displayLabel = col.uppercase ? String(label).toUpperCase() : label;
        return `<span class="badge bg-${badgeColor}-subtle text-${badgeColor} border border-${badgeColor}-subtle px-2 py-1">${displayLabel}</span>`;
    },

    /**
     * Truncates text if it exceeds a specified length.
     */
    truncate: (cell, col) => {
        if (typeof cell === 'string' && cell.length > col.truncate) {
            return cell.substring(0, col.truncate) + '...';
        }
        return cell;
    }
};
