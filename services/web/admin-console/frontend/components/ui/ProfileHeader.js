import { LinkGauge } from './Gauge.js';
import { ensureDynamicClass, isCssColor } from '../../renderer/engine/themeTokens.js';

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
        const iconDynamicClass = ensureDynamicClass(
            'phicon',
            `background:${hexToRgba(color, 0.14)};color:${color};`
        );
        const valueDynamicClass = ensureDynamicClass('phvalue', `color:${color};`);
        return {
            iconClass: `d-inline-flex align-items-center justify-content-center rounded-3 fs-5 profile-tone-icon ${iconDynamicClass}`,
            valueClass: valueDynamicClass || '',
        };
    }
    return {
        iconClass: `d-inline-flex align-items-center justify-content-center rounded-3 fs-5 profile-tone-icon bg-${color}-subtle text-${color}`,
        valueClass: `text-${color}`,
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
                        <div class="p-3 rounded-3 border profile-signal-panel">
                            <div class="d-flex align-items-center mb-2">
                                <i class="ri-lightbulb-flash-line text-warning me-2 fs-5"></i>
                                <h6 class="mb-0 fs-12 text-uppercase text-muted">Razonamiento del score</h6>
                            </div>
                            <p class="mb-0 fs-13 text-muted profile-reasoning-text">
                                ${reasoningText}
                            </p>
                        </div>
                    </div>

                    <!-- Column 2: Status & Intent -->
                    <div class="col-md-6">
                        <div class="d-flex flex-column align-items-stretch ps-md-4 pt-3 pt-md-0">
                            <div class="p-3 rounded-3 border w-100 profile-signal-panel">
                                <div class="d-flex align-items-center mb-2">
                                    <i class="ri-focus-3-line text-muted me-2 fs-5"></i>
                                    <h6 class="mb-0 fs-12 text-uppercase text-muted">Señales clave</h6>
                                </div>
                                <div class="d-flex flex-column gap-2">
                                    <div class="d-flex align-items-center gap-3 p-2 rounded-3 profile-signal-row">
                                        <div class="${intentTone.iconClass}">
                                            <i class="${intentIcon}"></i>
                                        </div>
                                        <div class="flex-grow-1 profile-signal-content">
                                            <div class="fs-11 text-muted text-uppercase mb-1 profile-signal-label">Intención</div>
                                            <div class="fw-semibold ${intentTone.valueClass}">${intentLabel}</div>
                                        </div>
                                    </div>
                                    <div class="d-flex align-items-center gap-3 p-2 rounded-3 profile-signal-row">
                                        <div class="${statusTone.iconClass}">
                                            <i class="${statusIcon}"></i>
                                        </div>
                                        <div class="flex-grow-1 profile-signal-content">
                                            <div class="fs-11 text-muted text-uppercase mb-1 profile-signal-label">Prioridad</div>
                                            <div class="fw-semibold ${statusTone.valueClass}">${statusLabel}</div>
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
