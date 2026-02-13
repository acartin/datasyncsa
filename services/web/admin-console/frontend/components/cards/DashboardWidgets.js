export function LinkMemberListCard(data) {
    const title = data.title || 'Members';
    const members = data.members || [];
    const createSchema = data.createSchema || '';

    const membersHtml = members.map(member => `
        <div class="d-flex align-items-center mb-3">
            <div class="flex-shrink-0">
                <img src="${member.avatar}" alt="" class="avatar-xs rounded-circle">
            </div>
            <div class="flex-grow-1 ms-2">
                <h6 class="mb-0 fs-14">${member.name}</h6>
                <p class="text-muted mb-0 fs-12">${member.position}</p>
            </div>
            <div class="flex-shrink-0">
                ${data.createSchema ? `
                    <div class="dropdown">
                        <button class="btn btn-icon btn-sm btn-ghost-primary" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                            <i class="ri-more-2-fill fs-14"></i>
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item" href="javascript:void(0);" 
                                onclick="window.handleEditAction(event, '${member.id}', '/contacts/{id}', '${member.editSchema}')">
                                <i class="ri-pencil-fill align-bottom me-2 text-muted"></i> Editar
                            </a></li>
                            ${member.convertSchema ? `
                            <li><a class="dropdown-item" href="javascript:void(0);" 
                                onclick="window.handleActionModal(event, '${member.id}', '/contacts/{id}/convert', '${member.convertSchema}', 'POST', 'Configurar Acceso')">
                                <i class="ri-key-2-fill align-bottom me-2 text-muted"></i> Dar Acceso
                            </a></li>
                            ` : ''}
                            <li><a class="dropdown-item text-danger" href="javascript:void(0);" 
                                onclick="window.deleteItem(event, '/contacts/${member.id}', '¿Eliminar contacto?')">
                                <i class="ri-delete-bin-fill align-bottom me-2"></i> Eliminar
                            </a></li>
                        </ul>
                    </div>
                ` : ''}
            </div>
        </div>
    `).join('');

    // "New Contact" Button Configuration
    const newBtnHtml = createSchema ? `
        <button type="button" class="btn btn-soft-success btn-sm"
                data-action="modal-form"
                data-url="/contacts"
                data-method="POST"
                data-title="Nuevo Contacto"
                data-schema="${createSchema}"
                onclick="window.handleGenericAction(this)">
            <i class="ri-add-line align-bottom me-1"></i> Nuevo
        </button>
    ` : '<button type="button" class="btn btn-soft-primary btn-sm">Ver Todos</button>';

    return `
        <div class="card">
            <div class="card-header align-items-center d-flex">
                <h4 class="card-title mb-0 flex-grow-1">${title}</h4>
                <div class="flex-shrink-0">
                    ${newBtnHtml}
                </div>
            </div>
            <div class="card-body">
                <div class="p-2">
                    ${membersHtml}
                </div>
            </div>
        </div>
    `;
}

export function LinkGenericCard(data) {
    const title = data.title || '';
    const content = data.contentHtml || '';

    return `
        <div class="card">
            ${title ? `<div class="card-header"><h4 class="card-title mb-0">${title}</h4></div>` : ''}
            <div class="card-body">
                ${content}
            </div>
        </div>
    `;
}

export function LinkFileGrid(data) {
    const title = data.title || 'Documentos';
    const files = data.files || [];

    if (!files || files.length === 0) {
        return `
            <div class="card">
                <div class="card-body text-center p-5">
                    <div class="text-muted">
                        <i class="ri-folder-unknow-line display-5"></i>
                        <p class="mt-2">No hay documentos disponibles.</p>
                    </div>
                </div>
            </div>
        `;
    }

    const filesHtml = files.map(file => {
        let icon = 'ri-file-text-line';
        let color = 'primary';

        // Safety check for filename
        const filename = file.filename || 'unknown.file';
        const ext = filename.split('.').pop().toLowerCase();

        if (['pdf'].includes(ext)) { icon = 'ri-file-pdf-line'; color = 'danger'; }
        else if (['doc', 'docx'].includes(ext)) { icon = 'ri-file-word-line'; color = 'primary'; }
        else if (['xls', 'xlsx', 'csv'].includes(ext)) { icon = 'ri-file-excel-line'; color = 'success'; }
        else if (['jpg', 'jpeg', 'png', 'gif'].includes(ext)) { icon = 'ri-image-line'; color = 'warning'; }

        return `
            <div class="col-xxl-3 col-md-4 col-sm-6">
                <div class="card border shadow-none">
                    <div class="card-body p-4 text-center">
                        <div class="avatar-md mx-auto mb-3">
                            <div class="avatar-title bg-soft-${color} text-${color} fs-24 rounded-circle">
                                <i class="${icon}"></i>
                            </div>
                        </div>
                        <h5 class="card-title fs-13 mb-1 text-truncate">${filename}</h5>
                        <p class="text-muted mb-0 fs-12">${file.created_at || ''}</p>
                    </div>
                    <div class="card-footer bg-transparent border-top-0 pt-0 text-center">
                        <a href="/documents/${file.id}/download" target="_blank" class="btn btn-sm btn-ghost-${color} w-100">
                            Download <i class="ri-download-2-line align-bottom ms-1"></i>
                        </a>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    return `
        <div>
            ${title ? `<h5 class="mb-3">${title}</h5>` : ''}
            <div class="row">
                ${filesHtml}
            </div>
        </div>
    `;
}

export function LinkContactListDetailed(data) {
    const title = data.title || 'Contactos Clave';
    const members = data.members || [];
    const createSchema = data.createSchema || '';

    // "New Contact" Button (Header)
    const newBtnHtml = createSchema ? `
        <button type="button" class="btn btn-soft-success btn-sm"
                data-action="modal-form"
                data-url="/contacts"
                data-method="POST"
                data-title="Nuevo Contacto"
                data-schema="${createSchema}"
                onclick="window.handleGenericAction(this)">
            <i class="ri-add-line align-bottom me-1"></i> Nuevo
        </button>
    ` : '';

    if (members.length === 0) {
        return `
            <div class="card">
                <div class="card-header align-items-center d-flex">
                    <h5 class="card-title mb-0 flex-grow-1">${title}</h5>
                    <div class="flex-shrink-0">${newBtnHtml}</div>
                </div>
                <div class="card-body text-center p-4">
                    <p class="text-muted mb-0">No hay contactos registrados.</p>
                </div>
            </div>
        `;
    }

    const membersHtml = members.map(member => {
        // Parse channels
        const channels = member.channels || [];
        const channelsHtml = channels.map(c => {
            let icon = c.category_icon || 'ri-question-line'; // Use DB icon first
            let val = c.value || '';

            // Fallback inference if no category icon
            if (!c.category_icon) {
                if (c.type === 'email' || val.includes('@')) icon = 'ri-mail-line';
                else if (c.type === 'phone') icon = 'ri-phone-line';
                else if (c.type === 'whatsapp') icon = 'ri-whatsapp-line';
            }

            return `<li><i class="${icon} me-2 align-middle text-muted fs-16"></i>${val}</li>`;
        }).join('');

        return `
            <div class="pt-3 border-top custom-border-top first-border-0">
                <ul class="list-unstyled mb-0 vstack gap-3">
                    <li>
                        <div class="d-flex align-items-center">
                            <div class="flex-shrink-0">
                                ${member.is_active
                ? '<div class="avatar-xs"><span class="avatar-title bg-success-subtle text-success rounded fs-15"><i class="ri-user-follow-line"></i></span></div>'
                : '<div class="avatar-xs"><span class="avatar-title bg-danger-subtle text-danger rounded fs-15"><i class="ri-user-unfollow-line"></i></span></div>'
            }
                            </div>
                            <div class="flex-grow-1 ms-3">
                                <h6 class="fs-14 mb-1">${member.name}</h6>
                                <p class="text-muted mb-0">${member.position}</p>
                            </div>
                            <div class="flex-shrink-0">
                                ${data.createSchema ? `
                                    <div class="dropdown">
                                        <button class="btn btn-icon btn-sm btn-ghost-primary" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                                            <i class="ri-more-2-fill fs-14"></i>
                                        </button>
                                        <ul class="dropdown-menu dropdown-menu-end">
                                            <li><a class="dropdown-item" href="javascript:void(0);" 
                                                onclick="window.handleEditAction(event, '${member.id}', '/contacts/{id}', '${member.editSchema}')">
                                                <i class="ri-pencil-fill align-bottom me-2 text-muted"></i> Editar
                                            </a></li>
                                            ${member.convertSchema ? `
                                            <li><a class="dropdown-item" href="javascript:void(0);" 
                                                onclick="window.handleActionModal(event, '${member.id}', '/contacts/{id}/convert', '${member.convertSchema}', 'POST', 'Configurar Acceso')">
                                                <i class="ri-key-2-fill align-bottom me-2 text-muted"></i> Dar Acceso
                                            </a></li>
                                            ` : ''}
                                            <li><a class="dropdown-item text-danger" href="javascript:void(0);" 
                                                onclick="window.deleteItem(event, '/contacts/${member.id}', '¿Eliminar contacto?')">
                                                <i class="ri-delete-bin-fill align-bottom me-2"></i> Eliminar
                                            </a></li>
                                        </ul>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </li>
                    ${channelsHtml}
                </ul>
            </div>
        `;
    }).join('');

    return `
        <div class="card">
            <div class="card-header align-items-center d-flex">
                <h5 class="card-title flex-grow-1 mb-0">${title}</h5>
                <div class="flex-shrink-0">
                    ${newBtnHtml}
                </div>
            </div>
            <div class="card-body">
                <div class="vstack gap-2">
                   ${membersHtml}
                </div>
            </div>
        </div>
    `;
}
