export function LinkProjectBanner(data) {
    const banner = data.banner || {};
    return `
        <div class="row">
            <div class="col-lg-12">
                <div class="card mt-n4 mx-n4 border-0">
                    <div class="bg-primary-subtle">
                        <div class="card-body pb-0 px-4">
                            <div class="row mb-3">
                                <div class="col-md">
                                    <div class="row align-items-center g-3">
                                        <div class="col-md-auto">
                                            <div class="avatar-md">
                                                <div class="avatar-title bg-white rounded-circle">
                                                    <img src="${banner.avatar}" alt="" class="avatar-sm">
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md">
                                            <div>
                                                <h4 class="fw-bold">${banner.title}</h4>
                                                <div class="hstack gap-3 flex-wrap">
                                                    <div><i class="ri-building-line align-bottom me-1"></i> ${banner.subtitle}</div>
                                                    <div class="vr"></div>
                                                    <div>Fecha Creación : <span class="fw-medium">${banner.create_date}</span></div>
                                                    <div class="vr"></div>
                                                    <div>Vencimiento : <span class="fw-medium">${banner.due_date}</span></div>
                                                    <div class="vr"></div>
                                                    <div class="badge rounded-pill bg-info fs-12">${banner.status}</div>
                                                    <div class="badge rounded-pill bg-danger fs-12">${banner.priority}</div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-auto">
                                    <div class="hstack gap-1 flex-wrap">
                                        <button type="button" class="btn btn-star btn-icon btn-sm fs-16 material-shadow-none">
                                            <i class="ri-star-fill text-warning"></i>
                                        </button>
                                        <button type="button" class="btn btn-icon btn-sm btn-ghost-primary fs-16 material-shadow-none">
                                            <i class="ri-share-line"></i>
                                        </button>
                                        <button type="button" class="btn btn-icon btn-sm btn-ghost-primary fs-16 material-shadow-none">
                                            <i class="ri-more-fill"></i>
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <ul class="nav nav-tabs-custom border-bottom-0" role="tablist">
                                <li class="nav-item">
                                    <a class="nav-link active fw-semibold" data-bs-toggle="tab" href="#project-overview" role="tab">
                                        Resumen
                                    </a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link fw-semibold" data-bs-toggle="tab" href="#project-documents" role="tab">
                                        Documentos
                                    </a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link fw-semibold" data-bs-toggle="tab" href="#project-activities" role="tab">
                                        Actividad
                                    </a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link fw-semibold" data-bs-toggle="tab" href="#project-team" role="tab">
                                        Equipo
                                    </a>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}
