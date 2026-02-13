import { safeBtoa } from '../../utils/base64.js';

export function resolveActionUrl(action = {}, context = {}) {
    let url = action.url || action.action_url || '';
    Object.entries(context).forEach(([key, value]) => {
        const token = `{${key}}`;
        if (url.includes(token)) {
            url = url.replace(new RegExp(`\\{${key}\\}`, 'g'), String(value ?? ''));
        }
    });
    return url;
}

export function resolveSchemaB64(action = {}, options = {}) {
    const { formSchema = null, fallbackSchema = null } = options;

    if (action.schema) {
        return typeof action.schema === 'string'
            ? action.schema
            : safeBtoa(JSON.stringify(action.schema));
    }

    if (Array.isArray(formSchema)) {
        return safeBtoa(JSON.stringify(formSchema));
    }

    if (typeof fallbackSchema === 'string' && fallbackSchema.length > 0) {
        return safeBtoa(fallbackSchema);
    }

    return safeBtoa('[]');
}
