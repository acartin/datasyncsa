/**
 * Safe UTF-8 Base64 Encode
 */
export function safeBtoa(str) {
    try {
        return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, function (match, p1) {
            return String.fromCharCode('0x' + p1);
        }));
    } catch (e) {
        return btoa(str);
    }
}

/**
 * Safe UTF-8 Base64 Decode
 */
export function safeAtob(str) {
    try {
        return decodeURIComponent(atob(str).split('').map(function (c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
    } catch (e) {
        // Fallback for non-UTF8 base64
        return atob(str);
    }
}
