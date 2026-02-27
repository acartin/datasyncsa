function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatDateTimeForUserLocale(value) {
    if (value === null || value === undefined || value === '') return '';

    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);

    const locale = (typeof navigator !== 'undefined' && (navigator.language || (navigator.languages && navigator.languages[0])))
        ? (navigator.language || navigator.languages[0])
        : 'es-CR';

    try {
        return new Intl.DateTimeFormat(locale, {
            dateStyle: 'medium',
            timeStyle: 'short',
        }).format(date);
    } catch (_error) {
        return date.toLocaleString();
    }
}

function formatFieldValue(value) {
    if (value === null || value === undefined || value === '') {
        return '<span class="text-muted">-</span>';
    }

    if (typeof value === 'object') {
        const pretty = escapeHtml(JSON.stringify(value, null, 2));
        return `<pre class="audit-json mb-0">${pretty}</pre>`;
    }

    return `<span>${escapeHtml(String(value))}</span>`;
}

function normalizeFields(props) {
    const source = Array.isArray(props.extracted_fields) ? props.extracted_fields : [];
    return source
        .filter((item) => item && typeof item === 'object')
        .map((item) => ({
            key: String(item.key || ''),
            label: String(item.label || item.key || 'Campo'),
            value: item.value,
        }));
}

function normalizeEvidenceGroups(props) {
    const groups = Array.isArray(props.evidence_groups) ? props.evidence_groups : [];
    return groups
        .filter((group) => group && typeof group === 'object')
        .map((group) => ({
            criterionLabel: String(group.criterion_label || group.criterion_key || 'Criterio'),
            data: group.data && typeof group.data === 'object' ? group.data : {},
        }))
        .filter((group) => Object.keys(group.data).length > 0);
}

function formatRole(role) {
    const normalized = String(role || '').trim().toLowerCase();
    if (normalized === 'assistant' || normalized === 'bot' || normalized === 'ai') {
        return { key: 'assistant', label: 'Asesor IA' };
    }
    if (normalized === 'user' || normalized === 'lead' || normalized === 'client') {
        return { key: 'user', label: 'Lead' };
    }
    return { key: 'system', label: 'Sistema' };
}

function normalizeMessages(props) {
    const source = Array.isArray(props.chat_messages) ? props.chat_messages : [];
    return source
        .filter((item) => item && typeof item === 'object')
        .map((item, idx) => {
            const content = String(item.content || '').trim();
            if (!content) return null;
            const role = formatRole(item.role);
            return {
                id: String(item.id || `msg-${idx}`),
                roleKey: role.key,
                roleLabel: role.label,
                content: escapeHtml(content),
                timestamp: escapeHtml(formatDateTimeForUserLocale(item.timestamp || '')),
            };
        })
        .filter(Boolean);
}

export function LinkAuditSplitView(component) {
    const props = component.properties || {};
    const fields = normalizeFields(props);
    const evidenceGroups = normalizeEvidenceGroups(props);
    const messages = normalizeMessages(props);
    const meta = (props.chat_meta && typeof props.chat_meta === 'object') ? props.chat_meta : {};
    const leftTitle = escapeHtml(String(props.left_title || 'Extracted data'));
    const rightTitle = escapeHtml(String(props.right_title || 'Reconstruccion del chat'));
    const auditId = `audit-${Math.random().toString(36).slice(2, 8)}`;

    const fieldsHtml = fields.length
        ? fields.map((field) => `
            <div class="audit-field-row">
                <div class="audit-field-label">${escapeHtml(field.label)}</div>
                <div class="audit-field-value">${formatFieldValue(field.value)}</div>
            </div>
        `).join('')
        : `<div class="text-muted small">No hay campos extraidos disponibles.</div>`;

    const evidenceHtml = evidenceGroups.length
        ? `
            <div class="audit-block mt-3">
                <div class="audit-section-title">Evidencia por pilar</div>
                ${evidenceGroups.map((group) => `
                    <div class="audit-evidence-item">
                        <div class="audit-evidence-title">${escapeHtml(group.criterionLabel)}</div>
                        <pre class="audit-json mb-0">${escapeHtml(JSON.stringify(group.data, null, 2))}</pre>
                    </div>
                `).join('')}
            </div>
        `
        : '';

    const messagesHtml = messages.length
        ? messages.map((message) => `
            <div class="audit-msg-row audit-msg-${message.roleKey}">
                <div class="audit-msg-bubble">
                    <div class="audit-msg-role">${message.roleLabel}</div>
                    <div class="audit-msg-text">${message.content}</div>
                    ${message.timestamp ? `<div class="audit-msg-time">${message.timestamp}</div>` : ''}
                </div>
            </div>
        `).join('')
        : `
            <div class="audit-empty-chat">
                <i class="ri-chat-off-line fs-2 text-muted"></i>
                <p class="mb-0 mt-2 text-muted">No hay mensajes para reconstruir.</p>
            </div>
        `;

    const chatMeta = [
        `${Number(meta.total_messages || 0)} mensajes`,
        meta.platform ? String(meta.platform) : '',
        meta.last_message_at ? formatDateTimeForUserLocale(meta.last_message_at) : '',
    ].filter(Boolean).map(escapeHtml).join(' · ');

    const summaryHtml = meta.summary
        ? `<div class="audit-chat-summary">${escapeHtml(String(meta.summary))}</div>`
        : '';

    return `
        <style>
            .audit-layout-${auditId} {
                display: grid;
                grid-template-columns: minmax(280px, 34%) minmax(0, 1fr);
                gap: 16px;
            }
            .audit-panel {
                border: 1px solid var(--vz-border-color);
                border-radius: 12px;
                background: var(--vz-secondary-bg);
                min-height: 560px;
                overflow: hidden;
            }
            .audit-panel-head {
                padding: 12px 14px;
                border-bottom: 1px solid var(--vz-border-color);
                background: color-mix(in srgb, var(--vz-body-bg), transparent 25%);
            }
            .audit-panel-title {
                margin: 0;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.04em;
                text-transform: uppercase;
                color: var(--vz-secondary-color);
            }
            .audit-left-scroll {
                max-height: 515px;
                overflow-y: auto;
                padding: 12px;
            }
            .audit-block {
                border: 1px solid var(--vz-border-color);
                border-radius: 10px;
                background: var(--vz-body-bg);
                padding: 10px;
            }
            .audit-field-row + .audit-field-row {
                margin-top: 10px;
                padding-top: 10px;
                border-top: 1px dashed var(--vz-border-color-translucent, var(--vz-border-color));
            }
            .audit-field-label {
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                color: var(--vz-secondary-color);
                margin-bottom: 4px;
            }
            .audit-field-value {
                font-size: 14px;
                color: var(--vz-body-color);
                word-break: break-word;
            }
            .audit-section-title {
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                color: var(--vz-secondary-color);
                margin-bottom: 8px;
            }
            .audit-evidence-item + .audit-evidence-item {
                margin-top: 10px;
            }
            .audit-evidence-title {
                font-size: 12px;
                font-weight: 600;
                color: var(--vz-body-color);
                margin-bottom: 6px;
            }
            .audit-json {
                max-height: 180px;
                overflow: auto;
                padding: 8px;
                border-radius: 8px;
                border: 1px solid var(--vz-border-color);
                background: var(--vz-body-bg);
                color: var(--vz-body-color);
                font-size: 12px;
            }
            .audit-chat-meta {
                margin-top: 4px;
                font-size: 12px;
                color: var(--vz-secondary-color);
            }
            .audit-chat-summary {
                margin-top: 8px;
                font-size: 12px;
                color: var(--vz-body-color);
            }
            .audit-chat-body {
                max-height: 515px;
                overflow-y: auto;
                padding: 14px;
                background:
                    radial-gradient(circle at 15% 15%, color-mix(in srgb, var(--vz-primary), transparent 92%), transparent 45%),
                    radial-gradient(circle at 85% 85%, color-mix(in srgb, var(--vz-info), transparent 93%), transparent 45%),
                    var(--vz-body-bg);
            }
            .audit-msg-row {
                display: flex;
                margin-bottom: 10px;
            }
            .audit-msg-row.audit-msg-user {
                justify-content: flex-end;
            }
            .audit-msg-row.audit-msg-assistant {
                justify-content: flex-start;
            }
            .audit-msg-row.audit-msg-system {
                justify-content: center;
            }
            .audit-msg-bubble {
                max-width: min(88%, 720px);
                border-radius: 12px;
                border: 1px solid var(--vz-border-color);
                padding: 10px 12px;
                background: var(--vz-secondary-bg);
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
            }
            .audit-msg-user .audit-msg-bubble {
                background: color-mix(in srgb, var(--vz-success), transparent 88%);
                border-color: color-mix(in srgb, var(--vz-success), transparent 60%);
            }
            .audit-msg-assistant .audit-msg-bubble {
                background: color-mix(in srgb, var(--vz-info), transparent 90%);
                border-color: color-mix(in srgb, var(--vz-info), transparent 62%);
            }
            .audit-msg-system .audit-msg-bubble {
                background: color-mix(in srgb, var(--vz-secondary-color), transparent 90%);
            }
            .audit-msg-role {
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--vz-secondary-color);
                margin-bottom: 4px;
            }
            .audit-msg-text {
                white-space: pre-wrap;
                overflow-wrap: anywhere;
                color: var(--vz-body-color);
                font-size: 14px;
                line-height: 1.42;
            }
            .audit-msg-time {
                margin-top: 6px;
                font-size: 11px;
                color: var(--vz-secondary-color);
            }
            .audit-empty-chat {
                min-height: 240px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                border: 1px dashed var(--vz-border-color);
                border-radius: 10px;
                background: var(--vz-secondary-bg);
            }
            @media (max-width: 992px) {
                .audit-layout-${auditId} {
                    grid-template-columns: 1fr;
                }
                .audit-panel {
                    min-height: 420px;
                }
                .audit-left-scroll,
                .audit-chat-body {
                    max-height: 360px;
                }
            }
        </style>
        <div class="audit-layout-${auditId}">
            <section class="audit-panel">
                <div class="audit-panel-head">
                    <h6 class="audit-panel-title">${leftTitle}</h6>
                </div>
                <div class="audit-left-scroll">
                    <div class="audit-block">
                        ${fieldsHtml}
                    </div>
                    ${evidenceHtml}
                </div>
            </section>

            <section class="audit-panel">
                <div class="audit-panel-head">
                    <h6 class="audit-panel-title">${rightTitle}</h6>
                    ${chatMeta ? `<div class="audit-chat-meta">${chatMeta}</div>` : ''}
                    ${summaryHtml}
                </div>
                <div class="audit-chat-body">
                    ${messagesHtml}
                </div>
            </section>
        </div>
    `;
}
