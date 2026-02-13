
import { LinkGauge } from './Gauge.js';

export function LinkProfileHeader(component) {
    const props = component.properties || {};

    const fullName = props.full_name || 'Sin Nombre';
    const email = props.email || '';
    const phone = props.phone || '';
    const contactText = [email, phone].filter(Boolean).join(' • ');

    // Score Gauge Logic
    const gaugeHtml = LinkGauge({
        properties: {
            value: props.score_value || 0,
            color: props.score_color || 'primary',
            size: 60,
            stroke: 5
        }
    });

    // Intent Data
    const intentLabel = props.intent_label || 'No definida';
    const intentColor = props.intent_color || 'primary';
    const intentIcon = props.intent_icon || 'ri-chat-1-line';

    // Status Data
    const statusLabel = props.status_label || 'Nuevo';
    const statusColor = props.status_color || 'warning';
    const statusIcon = props.status_icon || 'ri-loader-2-line';

    return `
        <div class="card profile-widget mb-3">
            <div class="card-body">
                <div class="row">
                    <!-- Column 1: Identity & Actions -->
                    <div class="col-md-6 border-end-md">
                        <div class="d-flex align-items-center mb-3">
                            <div class="flex-shrink-0 me-3">
                                ${gaugeHtml}
                            </div>
                            <div class="flex-grow-1">
                                <h4 class="mb-1">${fullName}</h4>
                                <p class="text-muted mb-0">${contactText}</p>
                            </div>
                        </div>
                        <div class="d-flex gap-2">
                             <button class="btn btn-sm btn-soft-success"><i class="ri-phone-line me-1"></i> Llamar</button>
                             <button class="btn btn-sm btn-soft-warning"><i class="ri-mail-line me-1"></i> Email</button>
                             <button class="btn btn-sm btn-ghost-secondary"><i class="ri-more-2-fill"></i></button>
                        </div>
                    </div>

                    <!-- Column 2: Status & Intent -->
                    <div class="col-md-6">
                        <div class="d-flex flex-column align-items-start gap-4 ps-md-4 pt-3 pt-md-0">
                            <!-- Intención -->
                            <div class="d-flex align-items-center gap-3">
                                <div class="avatar-sm flex-shrink-0">
                                    <div class="avatar-title bg-${intentColor}-subtle text-${intentColor} rounded-circle fs-3">
                                        <i class="${intentIcon}"></i>
                                    </div>
                                </div>
                                <div class="text-start">
                                    <h5 class="fs-13 mb-1 text-muted">Intención</h5>
                                    <h4 class="mb-0 fw-bold text-${intentColor}">${intentLabel}</h4>
                                </div>
                            </div>
                            <!-- Estado -->
                            <div class="d-flex align-items-center gap-3">
                                <div class="avatar-sm flex-shrink-0">
                                    <div class="avatar-title bg-${statusColor}-subtle text-${statusColor} rounded-circle fs-3">
                                        <i class="${statusIcon}"></i>
                                    </div>
                                </div>
                                <div class="text-start">
                                    <h5 class="fs-13 mb-1 text-muted">Estado</h5>
                                    <h4 class="mb-0 fw-bold text-${statusColor}">${statusLabel}</h4>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}
