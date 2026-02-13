/**
 * Component Registry for SDUI Renderer
 * Maps component types to their respective Link functions.
 */

import { LinkMetricCard } from '../../components/cards/MetricCard.js';
import { LinkGridContainer } from '../../components/grids/Grid.js';
import { LinkTypography } from '../../components/ui/Typography.js';
import { LinkButtonGroup } from '../../components/ui/ButtonGroup.js';

import { LinkLeadControlGrid } from '../../components/grids/LeadControlGrid.js';
import { LinkTabs } from '../../components/ui/Tabs.js';
import { LinkModalForm } from '../../components/forms/ModalForm.js';
import { LinkFormContainer } from '../../components/forms/FormContainer.js';
import { LinkRow, LinkCol } from '../../components/layout/Layout.js';
import { LinkProjectBanner } from '../../components/layout/ProjectBanner.js';
import { LinkCard } from '../../components/ui/Card.js';
import { LinkGauge } from '../../components/ui/Gauge.js';
import { LinkMemberListCard, LinkGenericCard, LinkFileGrid, LinkContactListDetailed } from '../../components/cards/DashboardWidgets.js';
import { LinkScoreRow } from '../../components/ui/ScoreRow.js';
import { LinkInfoRow } from '../../components/ui/InfoRow.js';
import { LinkProfileHeader } from '../../components/ui/ProfileHeader.js';
import { LinkBackLink } from '../../components/ui/BackLink.js';
import { LinkEmptyState } from '../../components/ui/EmptyState.js';

// Simple Wrapper for Custom Grid Container
import { LinkCustomGridContainer } from '../../components/grids/CustomGridContainer.js';

import { LinkGridVisual } from '../../components/grids/GridVisual.js';

const registry = {
    'custom-leads-grid': LinkCustomGridContainer, // Beta Engine
    'card': LinkCard,
    'card-metric': LinkMetricCard,
    'grid': LinkGridContainer,
    'typography': LinkTypography,
    'button-group': LinkButtonGroup,
    'grid-visual': LinkGridVisual,
    'grid-leads-control': LinkLeadControlGrid,
    'tabs': LinkTabs,
    'modal-form': LinkModalForm,
    'row': LinkRow,
    'col': LinkCol,
    'layout-row': LinkRow,
    'layout-col': LinkCol,
    'form-container': LinkFormContainer,
    'project-banner': LinkProjectBanner,
    'member-list': LinkMemberListCard,
    'member-list-card': LinkMemberListCard,
    'generic-card': LinkGenericCard,
    'gauge': LinkGauge,
    'file-grid': LinkFileGrid,
    'contact-list-detailed': LinkContactListDetailed,
    'score-row': LinkScoreRow,
    'info-row': LinkInfoRow,
    'profile-header': LinkProfileHeader,
    'back-link': LinkBackLink,
    'empty-state': LinkEmptyState
};

// --- GLOBAL FORM HANDLERS (Moved from FormContainer to ensure execution) ---

if (!window.validateFileSize) {
    window.validateFileSize = (input, helpId) => {
        const file = input.files[0];
        const helpText = document.getElementById(helpId);
        if (!file) {
            helpText.innerText = 'Max: 100MB';
            helpText.classList.remove('text-danger', 'text-success');
            helpText.classList.add('text-muted');
            return;
        }

        const sizeMB = file.size / (1024 * 1024);
        if (sizeMB > 100) {
            input.value = ''; // Clear input
            helpText.innerText = `Error: Archivo demasiado grande (${sizeMB.toFixed(2)} MB). Límite: 100MB`;
            helpText.classList.remove('text-muted', 'text-success');
            helpText.classList.add('text-danger');
        } else {
            helpText.innerText = `Tamaño: ${sizeMB.toFixed(2)} MB (OK)`;
            helpText.classList.remove('text-muted', 'text-danger');
            helpText.classList.add('text-success');
        }
    };
}

if (!window.handleFormSubmit) {
    window.handleFormSubmit = async (event, formId) => {
        event.preventDefault();
        console.log('--- Handle Form Submit Triggered ---');

        const form = document.getElementById(formId);
        const formData = new FormData(form);
        const action = form.getAttribute('action');
        const method = form.getAttribute('method');
        const btn = form.querySelector('button[type="submit"]');
        const originalText = btn.innerText;

        try {
            btn.disabled = true;
            btn.innerText = 'Guardando...';

            // Get auth token if available
            const token = localStorage.getItem('access_token');
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const fullUrl = window.AppConfig.API_BASE_URL + action;
            console.log('Sending to:', fullUrl);
            console.log('Token exists:', !!token);

            const response = await fetch(fullUrl, {
                method: method,
                headers: headers,
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || `Error ${response.status}`);
            }

            const result = await response.json();

            // Success Feedback
            btn.classList.replace('btn-primary', 'btn-success');
            btn.innerText = '¡Guardado!';
            setTimeout(() => {
                btn.classList.replace('btn-success', 'btn-primary');
                btn.innerText = originalText;
                btn.disabled = false;
            }, 2000);

        } catch (error) {
            console.error('Form Submit Error:', error);
            btn.classList.replace('btn-primary', 'btn-danger');
            btn.innerText = 'Error';
            setTimeout(() => {
                btn.classList.replace('btn-danger', 'btn-primary');
                btn.innerText = originalText;
                btn.disabled = false;
            }, 2000);
        }
    };
}


export function renderComponent(component) {
    if (!component || !component.type) return '';

    const LinkFn = registry[component.type];
    if (LinkFn) {
        return LinkFn(component);
    }

    // console.warn(`[Renderer] Missing component type: ${ component.type } `);
    return `< div class= "alert alert-warning" > Unknown component: ${component.type}</div > `;
}

export function renderContent(components) {
    if (!components) return '';
    if (!Array.isArray(components)) return renderComponent(components);
    return components.map(c => renderComponent(c)).join('');
}
