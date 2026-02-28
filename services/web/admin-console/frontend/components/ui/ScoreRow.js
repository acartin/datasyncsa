
import { ensureDynamicClass, isCssColor } from '../../renderer/engine/themeTokens.js';

export function LinkScoreRow(component) {
    const props = component.properties || {};

    const title = props.title || 'Metric';
    const score = parseInt(props.score || 0);
    const maxScore = parseInt(props.max_score || 30);
    const icon = props.icon || 'ri-checkbox-circle-line';
    const rawColor = props.color || 'thermal-none';
    const label = props.label || '-';
    const rawExplanation = (props.explanation || '').toString().trim();
    const explanation = rawExplanation
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    const hasCustomColor = isCssColor(rawColor);
    const isThermalClass = typeof rawColor === 'string' && rawColor.startsWith('thermal-');

    // Calculate percentage, capped at 100
    const percentage = Math.min(100, Math.max(0, (score / maxScore) * 100));

    const rowClasses = ['mb-4', 'score-row-component', 'score-row-layout'];
    const dynamicVars = [`--sr-percentage:${percentage}%;`];

    let iconClass = 'avatar-title rounded-3 fs-3 score-row-icon';
    let badgeClass = 'badge border score-row-badge';
    let progressClass = 'progress-bar score-row-progress-bar';

    if (hasCustomColor) {
        rowClasses.push('score-row-custom-color');
        dynamicVars.push(`--score-row-color:${rawColor};`);
    } else if (isThermalClass) {
        iconClass += ` ${rawColor}`;
        badgeClass += ` ${rawColor}`;
        progressClass += ` ${rawColor}`;
    } else {
        iconClass += ` bg-${rawColor}-subtle text-${rawColor}`;
        badgeClass += ` bg-${rawColor}-subtle text-${rawColor} border-${rawColor}-subtle`;
        progressClass += ` bg-${rawColor}`;
    }

    const explanationHtml = `
        <div class="score-row-explanation">
            <p class="mb-0 fs-14 text-muted text-break score-row-explanation-text" title="${explanation}">${explanation || '-'}</p>
        </div>
    `;
    const dynamicClass = ensureDynamicClass('srvars', dynamicVars.join(''));
    if (dynamicClass) rowClasses.push(dynamicClass);

    return `
        <div class="${rowClasses.join(' ')}">
            <!-- Pillar -->
            <div class="d-flex align-items-center score-row-main">
                <div class="avatar-sm flex-shrink-0 me-3">
                    <div class="${iconClass}">
                        <i class="${icon}"></i>
                    </div>
                </div>
                <div class="score-row-title-wrap">
                    <div class="d-flex align-items-center flex-wrap gap-2">
                        <h5 class="fs-13 mb-0 text-muted text-uppercase">${title}</h5>
                        <span class="${badgeClass}">${label}</span>
                    </div>
                </div>
            </div>

            <!-- Thermometer -->
            <div class="progress border score-row-progress">
                <div class="${progressClass}" role="progressbar" 
                     aria-valuenow="${score}" aria-valuemin="0" aria-valuemax="${maxScore}">
                </div>
            </div>

            <!-- Score -->
            <div class="text-start score-row-score">
                <h5 class="mb-0 fw-bold fs-4 text-muted">${score} <span class="fs-12 text-muted fw-normal">/${maxScore}</span></h5>
            </div>

            <!-- Explanation -->
            ${explanationHtml}
        </div>
    `;
}
