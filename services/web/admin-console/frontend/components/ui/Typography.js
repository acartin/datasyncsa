export function LinkTypography(data) {
    const tag = data.tag || 'p';
    const classes = [
        'col-12',
        'mb-3',
        data.class || '',
        data.color ? `text-${data.color}` : ''
    ].join(' ').trim();

    return `
        <div class="${classes}">
            <${tag}>${data.text}</${tag}>
        </div>
    `;
}
