
export function LinkScoreRow(component) {
    const props = component.properties || {};

    const title = props.title || 'Metric';
    const score = parseInt(props.score || 0);
    const maxScore = parseInt(props.max_score || 30);
    const icon = props.icon || 'ri-checkbox-circle-line';
    const color = props.color || 'primary';
    const label = props.label || '-';

    // Calculate percentage, capped at 100
    const percentage = Math.min(100, Math.max(0, (score / maxScore) * 100));

    // Unique ID for animation style scope if needed (though transition works without it)
    const animId = `score-anim-${Math.random().toString(36).substr(2, 5)}`;

    return `
        <div class="d-flex align-items-center mb-4 score-row-component">
            <!-- Icon -->
            <div class="avatar-sm flex-shrink-0 me-3">
                <div class="avatar-title bg-${color}-subtle text-${color} rounded-circle fs-3">
                    <i class="${icon}"></i>
                </div>
            </div>
            
            <!-- Title & Label -->
            <div class="flex-grow-1 me-3">
                 <div class="d-flex align-items-center">
                    <h5 class="fs-13 mb-0 text-muted text-uppercase me-2">${title}</h5>
                    <span class="badge bg-${color}-subtle text-${color} border border-${color}-subtle" style="font-size: 10px;">${label}</span>
                </div>
            </div>

            <!-- Gauge & Value -->
            <div class="d-flex align-items-center justify-content-end" style="min-width: 220px;">
                <!-- Linear Gauge -->
                <div class="progress flex-grow-1 border me-3" style="height: 20px; background-color: #cad3dc; max-width: 150px;">
                    <style>
                        @keyframes grow-${animId} {
                            from { width: 0; }
                            to { width: ${percentage}%; }
                        }
                    </style>
                    <div class="progress-bar bg-${color}" role="progressbar" 
                         style="width: ${percentage}%; animation: grow-${animId} 1s ease-out forwards;" 
                         aria-valuenow="${score}" aria-valuemin="0" aria-valuemax="${maxScore}">
                    </div>
                </div>
                
                <!-- Numeric Value -->
                <div class="text-end" style="width: 60px;">
                     <h5 class="mb-0 fw-bold fs-4 text-muted">${score} <span class="fs-12 text-muted fw-normal">/${maxScore}</span></h5>
                </div>
            </div>
        </div>
    `;
}
