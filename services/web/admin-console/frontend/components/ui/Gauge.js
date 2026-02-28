
import { ensureDynamicClass, resolveGaugeRampColor, resolveUiColor } from '../../renderer/engine/themeTokens.js';

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

    const explicitColor = resolveUiColor(props.color, '');
    const color = explicitColor || resolveGaugeRampColor(normalizedPct);

    const r = (size / 2) - (strokeWidth / 2);
    const cx = size / 2;
    const cy = size / 2;
    const c = 2 * Math.PI * r;
    const offset = c - normalizedPct * c;
    const fontSize = size * 0.28;
    const displayValue = Number.isInteger(clampedValue)
        ? String(clampedValue)
        : clampedValue.toFixed(1).replace(/\.0$/, '');

    const dynamicClass = ensureDynamicClass('gaugevars', `--gauge-size:${size}px;--gauge-c:${c};--gauge-offset:${offset};`);

    return `
        <div class="d-inline-flex align-items-center justify-content-center position-relative ac-gauge ${dynamicClass} ${props.class || ''}" title="Score: ${displayValue}/${maxScore}">
            <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
                <circle class="ac-gauge-track" cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="currentColor" stroke-width="${strokeWidth}"></circle>
                <circle class="ac-gauge-value" cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" 
                    stroke-dasharray="${c}" 
                    stroke-dashoffset="${c}"
                    stroke-linecap="round" 
                    transform="rotate(-90 ${cx} ${cy})"></circle>
                <text x="50%" y="54%" text-anchor="middle" dy=".1em" 
                      class="ac-gauge-value-text" font-size="${fontSize}" font-weight="700">${displayValue}</text>
            </svg>
        </div>
    `;
}
