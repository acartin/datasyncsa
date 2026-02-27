
export function LinkGauge(component) {
    const props = component.properties || {};
    const rawValue = Number(props.value ?? 0);
    const value = Number.isFinite(rawValue) ? rawValue : 0;
    const rawMaxScore = Number(props.max_score ?? props.max ?? 100);
    const maxScore = Number.isFinite(rawMaxScore) && rawMaxScore > 0 ? rawMaxScore : 100;
    const clampedValue = Math.min(maxScore, Math.max(0, value));
    const normalizedPct = clampedValue / maxScore;
    const size = parseInt(props.size || 48); // Slightly larger than grid (32)
    const strokeWidth = props.stroke || 4;

    // Map colors (Bootstrap + Thermal Palette matching index.html)
    let color = '#475569';
    const cReq = String(props.color || '').toLowerCase();

    if (cReq === 'danger' || cReq === 'thermal-extreme') color = '#f06548';
    else if (cReq === 'warning' || cReq === 'thermal-high') color = '#f7b84b';
    else if (cReq === 'primary' || cReq === 'thermal-mid') color = '#4b38b3';
    else if (cReq === 'success' || cReq === 'thermal-low') color = '#0ab39c';
    else if (cReq === 'info' || cReq === 'thermal-info') color = '#299cdb';
    else if (cReq === 'thermal-none') color = '#adb5bd';
    else if (props.color && props.color.startsWith('#')) color = props.color; // Custom hex

    // Fallback Color Logic (If no color prop provided)
    if (!props.color) {
        if (normalizedPct >= 0.9) color = '#f06548';      // Extreme
        else if (normalizedPct >= 0.7) color = '#f7b84b'; // High
        else if (normalizedPct >= 0.5) color = '#4b38b3'; // Mid
        else if (normalizedPct >= 0.2) color = '#0ab39c'; // Low
        else color = '#475569';                  // None
    }

    const r = (size / 2) - (strokeWidth / 2);
    const cx = size / 2;
    const cy = size / 2;
    const c = 2 * Math.PI * r;
    const offset = c - normalizedPct * c;
    const fontSize = size * 0.28;
    const displayValue = Number.isInteger(clampedValue)
        ? String(clampedValue)
        : clampedValue.toFixed(1).replace(/\.0$/, '');

    // Unique Animation ID to avoid conflicts if multiple gauges on screen
    const animId = `gauge-anim-${Math.random().toString(36).substr(2, 5)}`;

    return `
        <div class="d-inline-flex align-items-center justify-content-center position-relative ${props.class || ''}" 
             style="width: ${size}px; height: ${size}px;" title="Score: ${displayValue}/${maxScore}">
            <style>
                @keyframes ${animId} {
                    from { stroke-dashoffset: ${c}; }
                    to { stroke-dashoffset: ${offset}; }
                }
            </style>
            <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
                <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" style="opacity: 0.1"></circle>
                <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" 
                    stroke-dasharray="${c}" 
                    stroke-dashoffset="${c}"
                    stroke-linecap="round" 
                    transform="rotate(-90 ${cx} ${cy})"
                    style="animation: ${animId} 1.2s cubic-bezier(0.4, 0, 0.2, 1) forwards;"></circle>
                <text x="50%" y="54%" text-anchor="middle" dy=".1em" 
                      font-size="${fontSize}" font-weight="700" fill="#6c757d">${displayValue}</text>
            </svg>
        </div>
    `;
}
