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
        ? messages.map((message) => {
            if (message.roleKey === 'system') {
                return `
                    <li class="chat-day-title">
                        <span class="title">${message.content}</span>
                    </li>
                `;
            }

            const sideClass = message.roleKey === 'user' ? 'right' : 'left';
            const avatarHtml = message.roleKey === 'user'
                ? ''
                : `
                    <div class="chat-avatar">
                        <div class="avatar-xs">
                            <div class="avatar-title rounded-circle ${message.roleKey === 'assistant' ? 'bg-info-subtle text-info' : 'bg-secondary-subtle text-secondary'}">
                                ${message.roleKey === 'assistant' ? 'IA' : 'SYS'}
                            </div>
                        </div>
                    </div>
                `;

            return `
                <li class="chat-list ${sideClass}" id="audit-${escapeHtml(message.id)}">
                    <div class="conversation-list">
                        ${avatarHtml}
                        <div class="user-chat-content">
                            <div class="ctext-wrap">
                                <div class="ctext-wrap-content">
                                    <p class="mb-0 ctext-content">${message.content}</p>
                                </div>
                            </div>
                            <div class="conversation-name">
                                <span class="d-none name">${message.roleLabel}</span>
                                ${message.timestamp ? `<small class="text-muted time">${message.timestamp}</small>` : ''}
                            </div>
                        </div>
                    </div>
                </li>
            `;
        }).join('')
        : `
            <li>
                <div class="audit-empty-chat">
                    <i class="ri-chat-off-line fs-2 text-muted"></i>
                    <p class="mb-0 mt-2 text-muted">No hay mensajes para reconstruir.</p>
                </div>
            </li>
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
        <div class="audit-layout">
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
                <div class="chat-conversation p-3 p-lg-4 audit-chat-body">
                    <ul class="list-unstyled chat-conversation-list mb-0">
                        ${messagesHtml}
                    </ul>
                </div>
            </section>
        </div>
    `;
}
