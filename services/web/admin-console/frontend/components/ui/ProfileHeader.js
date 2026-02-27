
import { LinkGauge } from './Gauge.js';

function isCssColor(value) {
    if (typeof value !== 'string') return false;
    return (
        value.startsWith('#') ||
        value.startsWith('rgb(') ||
        value.startsWith('rgba(') ||
        value.startsWith('hsl(') ||
        value.startsWith('hsla(') ||
        value.startsWith('var(')
    );
}

function hexToRgba(hex, alpha = 0.16) {
    const normalized = String(hex || '').trim();
    if (!normalized.startsWith('#')) return `rgba(148, 163, 184, ${alpha})`;
    const raw = normalized.slice(1);
    const full = raw.length === 3
        ? raw.split('').map((c) => c + c).join('')
        : raw;
    if (full.length !== 6) return `rgba(148, 163, 184, ${alpha})`;
    const r = parseInt(full.slice(0, 2), 16);
    const g = parseInt(full.slice(2, 4), 16);
    const b = parseInt(full.slice(4, 6), 16);
    if ([r, g, b].some((n) => Number.isNaN(n))) {
        return `rgba(148, 163, 184, ${alpha})`;
    }
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function resolveTone(colorValue, fallbackToken) {
    const color = colorValue || fallbackToken;
    if (isCssColor(color)) {
        return {
            iconClass: 'd-inline-flex align-items-center justify-content-center rounded-3 fs-5',
            iconStyle: `width:40px;height:40px;background:${hexToRgba(color, 0.14)};color:${color};`,
            valueClass: '',
            valueStyle: `color:${color};`,
        };
    }
    return {
        iconClass: `d-inline-flex align-items-center justify-content-center rounded-3 fs-5 bg-${color}-subtle text-${color}`,
        iconStyle: 'width:40px;height:40px;',
        valueClass: `text-${color}`,
        valueStyle: '',
    };
}

export function LinkProfileHeader(component) {
    const props = component.properties || {};

    const fullName = props.full_name || 'Sin Nombre';
    const email = props.email || '';
    const phone = props.phone || '';
    const contactText = [email, phone].filter(Boolean).join(' • ');
    const reasoningRaw = (props.reasoning || '').toString().trim();
    const reasoningText = (reasoningRaw || 'Sin razonamiento disponible para este score.')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    const panelStyle = 'background-color: var(--vz-secondary-bg); border-color: var(--vz-border-color);';
    const signalRowStyle = 'background-color: var(--vz-body-bg); border: 1px solid var(--vz-border-color-translucent, var(--vz-border-color));';

    // Score Gauge Logic
    const gaugeHtml = LinkGauge({
        properties: {
            value: props.score_value || 0,
            max_score: 10,
            color: props.score_color || 'primary',
            size: 60,
            stroke: 5
        }
    });

    // Intent Data
    const intentLabel = props.intent_label || 'No definida';
    const intentColor = props.intent_color || 'primary';
    const intentIcon = props.intent_icon || 'ri-chat-1-line';
    const intentTone = resolveTone(intentColor, 'primary');

    // Status Data
    const statusLabel = props.status_label || 'Nuevo';
    const statusColor = props.status_color || 'warning';
    const statusIcon = props.status_icon || 'ri-loader-2-line';
    const statusTone = resolveTone(statusColor, 'warning');

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
                        <div class="p-3 rounded-3 border" style="${panelStyle}">
                            <div class="d-flex align-items-center mb-2">
                                <i class="ri-lightbulb-flash-line text-warning me-2 fs-5"></i>
                                <h6 class="mb-0 fs-12 text-uppercase text-muted">Razonamiento del score</h6>
                            </div>
                            <p class="mb-0 fs-13 text-muted" style="line-height: 1.45;">
                                ${reasoningText}
                            </p>
                        </div>
                    </div>

                    <!-- Column 2: Status & Intent -->
                    <div class="col-md-6">
                        <div class="d-flex flex-column align-items-stretch ps-md-4 pt-3 pt-md-0">
                            <div class="p-3 rounded-3 border w-100" style="${panelStyle}">
                                <div class="d-flex align-items-center mb-2">
                                    <i class="ri-focus-3-line text-muted me-2 fs-5"></i>
                                    <h6 class="mb-0 fs-12 text-uppercase text-muted">Señales clave</h6>
                                </div>
                                <div class="d-flex flex-column gap-2">
                                    <div class="d-flex align-items-center gap-3 p-2 rounded-3" style="${signalRowStyle}">
                                        <div class="${intentTone.iconClass}" style="${intentTone.iconStyle}">
                                            <i class="${intentIcon}"></i>
                                        </div>
                                        <div class="flex-grow-1" style="min-width: 0;">
                                            <div class="fs-11 text-muted text-uppercase mb-1" style="letter-spacing: .04em;">Intención</div>
                                            <div class="fw-semibold ${intentTone.valueClass}" style="${intentTone.valueStyle}">${intentLabel}</div>
                                        </div>
                                    </div>
                                    <div class="d-flex align-items-center gap-3 p-2 rounded-3" style="${signalRowStyle}">
                                        <div class="${statusTone.iconClass}" style="${statusTone.iconStyle}">
                                            <i class="${statusIcon}"></i>
                                        </div>
                                        <div class="flex-grow-1" style="min-width: 0;">
                                            <div class="fs-11 text-muted text-uppercase mb-1" style="letter-spacing: .04em;">Prioridad</div>
                                            <div class="fw-semibold ${statusTone.valueClass}" style="${statusTone.valueStyle}">${statusLabel}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}
