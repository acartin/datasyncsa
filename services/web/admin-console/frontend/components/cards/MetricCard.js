export function LinkMetricCard(data) {
    const color = data.color || 'primary';
    const label = data.label || 'Metric';
    const value = data.value || 'Active'; // Using value from data if available, defaulting to 'Active' based on previous static code

    return `
        <div class="col-xl-3 col-md-6">
            <div class="card card-animate border-${color}">
                <div class="card-body">
                    <div class="d-flex align-items-center">
                        <div class="flex-grow-1 overflow-hidden">
                            <p class="text-uppercase fw-medium text-muted text-truncate mb-0">
                                ${label}
                            </p>
                        </div>
                    </div>
                    <div class="d-flex align-items-end justify-content-between mt-4">
                        <div>
                            <h4 class="fs-22 fw-semibold ff-secondary mb-4">
                                <span class="counter-value" data-target="0">${value}</span>
                            </h4>
                            <span class="badge bg-${color}-subtle text-${color}">
                                Verified
                            </span>
                        </div>
                        <div class="avatar-sm flex-shrink-0">
                            <span class="avatar-title bg-${color}-subtle rounded fs-3">
                                <i class="ri-checkbox-circle-line text-${color}"></i>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}
