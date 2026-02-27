
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
    const isCssColor = typeof rawColor === 'string' && (
        rawColor.startsWith('#') ||
        rawColor.startsWith('rgb(') ||
        rawColor.startsWith('rgba(') ||
        rawColor.startsWith('hsl(') ||
        rawColor.startsWith('hsla(') ||
        rawColor.startsWith('var(')
    );
    const isThermalClass = typeof rawColor === 'string' && rawColor.startsWith('thermal-');

    // Calculate percentage, capped at 100
    const percentage = Math.min(100, Math.max(0, (score / maxScore) * 100));

    // Unique ID for animation style scope if needed (though transition works without it)
    const animId = `score-anim-${Math.random().toString(36).substr(2, 5)}`;

    let iconClass = 'avatar-title rounded-3 fs-3';
    let iconStyle = '';
    let badgeClass = 'badge border';
    let badgeStyle = 'font-size: 10px;';
    let progressClass = 'progress-bar';
    let progressInlineColor = '';

    if (isCssColor) {
        iconStyle = `color:${rawColor}; background: rgba(148, 163, 184, 0.16);`;
        badgeStyle += ` color:${rawColor}; border-color:${rawColor} !important; background: transparent;`;
        progressInlineColor = `background-color:${rawColor};`;
    } else if (isThermalClass) {
        iconClass += ` ${rawColor}`;
        iconStyle = 'background: rgba(148, 163, 184, 0.16);';
        badgeClass += ` ${rawColor}`;
        badgeStyle += ' border-color: currentColor !important; background: transparent;';
        progressClass += ` ${rawColor}`;
        progressInlineColor = 'background-color: currentColor;';
    } else {
        iconClass += ` bg-${rawColor}-subtle text-${rawColor}`;
        badgeClass += ` bg-${rawColor}-subtle text-${rawColor} border-${rawColor}-subtle`;
        progressClass += ` bg-${rawColor}`;
    }

    const explanationHtml = `
        <div class="score-row-explanation" style="min-width: 0; padding-left: 22px;">
            <p class="mb-0 fs-14 text-muted text-break" style="white-space: normal; overflow-wrap: anywhere;" title="${explanation}">${explanation || '-'}</p>
        </div>
    `;

    return `
        <style>
            .score-row-layout-${animId} {
                display: grid;
                grid-template-columns: minmax(180px, 21%) 150px 70px minmax(0, 1fr);
                column-gap: 6px;
                align-items: center;
            }
            @media (max-width: 992px) {
                .score-row-layout-${animId} {
                    grid-template-columns: minmax(160px, 1fr) 130px 60px;
                    row-gap: 8px;
                }
                .score-row-layout-${animId} .score-row-explanation {
                    grid-column: 1 / -1;
                }
            }
            @keyframes grow-${animId} {
                from { width: 0; }
                to { width: ${percentage}%; }
            }
        </style>
        <div class="mb-4 score-row-component score-row-layout-${animId}">
            <!-- Pillar -->
            <div class="d-flex align-items-center" style="min-width: 0;">
                <div class="avatar-sm flex-shrink-0 me-3">
                    <div class="${iconClass}" style="${iconStyle}">
                        <i class="${icon}"></i>
                    </div>
                </div>
                <div style="min-width: 0;">
                    <div class="d-flex align-items-center flex-wrap gap-2">
                        <h5 class="fs-13 mb-0 text-muted text-uppercase">${title}</h5>
                        <span class="${badgeClass}" style="${badgeStyle}">${label}</span>
                    </div>
                </div>
            </div>

            <!-- Thermometer -->
            <div class="progress border" style="height: 20px; background-color: #cad3dc; width: 150px;">
                <div class="${progressClass}" role="progressbar" 
                     style="width: ${percentage}%; animation: grow-${animId} 1s ease-out forwards; ${progressInlineColor}" 
                     aria-valuenow="${score}" aria-valuemin="0" aria-valuemax="${maxScore}">
                </div>
            </div>

            <!-- Score -->
            <div class="text-start" style="width: 64px;">
                <h5 class="mb-0 fw-bold fs-4 text-muted">${score} <span class="fs-12 text-muted fw-normal">/${maxScore}</span></h5>
            </div>

            <!-- Explanation -->
            ${explanationHtml}
        </div>
    `;
}
