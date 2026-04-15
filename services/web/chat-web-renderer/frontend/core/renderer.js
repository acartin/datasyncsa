/**
 * REALTOR CHAT: POLYMORPHIC RENDERER CORE
 * Este es el cerebro del frontend. Recibe un JSON del Bridge y decide qué dibujar.
 */

export class ChatRenderer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.botName = "";
    }

    setBotName(name) {
        this.botName = String(name || '').trim();
    }

    scrollToBottom() {
        this.container.scrollTop = this.container.scrollHeight;
    }

    renderResponse(sduiResponse) {
        const components = Array.isArray(sduiResponse?.components) ? sduiResponse.components : [];

        // Limpiamos mensajes de "Cargando..." si existen
        if (this.container.querySelector('.text-muted')) {
            this.container.innerHTML = '';
        }

        components.forEach((comp) => {
            const element = this.createComponent(comp);
            if (element) {
                const bubble = this.wrapInBubble(element, comp.sender || 'bot', comp.type);
                this.container.appendChild(bubble);
            }
        });

        // Scroll automático al final
        this.container.scrollTop = this.container.scrollHeight;
    }

    createComponent(config) {
        let el = null;

        switch (config.type) {
            case 'chat':
                el = document.createElement('div');
                el.innerText = config.text;
                break;

            case 'property-card':
                el = document.createElement('property-card-v2');
                el.title = config.title;
                el.price = config.price;
                el.currency = config.currency;
                el.priceNote = config.price_note;
                el.location = config.location;
                el.imageUrl = config.image_url;
                el.imageUrls = config.image_urls || [];
                el.photoCount = config.photo_count;
                el.publicUrl = config.public_url;
                el.features = config.features || {};
                el.tags = config.tags || [];
                el.badgeMain = config.badge_main;
                el.badgeSub = config.badge_sub;
                el.bedrooms = config.bedrooms_clean ?? config.features?.bedrooms_clean ?? config.features?.bedrooms;
                el.bathrooms = config.bathrooms_clean ?? config.features?.bathrooms_clean ?? config.features?.bathrooms;
                el.sqm = config.sqm_clean ?? config.features?.sqm_clean ?? config.features?.sqm ?? config.features?.area_display;
                el.garage = config.garage_clean ?? config.features?.garage_clean ?? config.features?.garage;
                el.amenities = config.amenities || config.features?.amenities || [];
                el.description = config.description || config.features?.description || '';
                break;

            case 'property-grid':
                el = document.createElement('property-grid');
                el.title = config.title;
                el.properties = config.properties;
                break;

            case 'action-menu':
                el = document.createElement('action-menu');
                el.options = config.options;
                break;

            case 'mortgage-calculator':
                el = document.createElement('mortgage-calculator');
                el.propertyPrice = config.property_price;
                el.defaultInterest = config.default_interest;
                break;

            case 'property-map':
                el = document.createElement('property-map');
                el.center = config.center;
                el.zoom = config.zoom;
                el.pois = config.pois;
                break;

            case 'photo-carousel':
                el = document.createElement('photo-carousel');
                el.images = config.images;
                el.showThumbnails = config.show_thumbnails;
                break;

            default:
                console.warn(`Componente desconocido: ${config.type}`);
        }

        return el;
    }

    showTyping() {
        const indicator = document.createElement('div');
        indicator.id = 'typing-indicator';
        indicator.className = 'typing-indicator';
        indicator.innerHTML = '<span></span><span></span><span></span>';
        this.container.appendChild(indicator);
        this.container.scrollTop = this.container.scrollHeight;
    }

    hideTyping() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }

    wrapInBubble(element, sender, componentType = 'chat') {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${sender}`;
        wrapper.dataset.componentType = componentType;

        const senderLabel = sender === 'user' ? 'Tú' : this.botName;
        if (senderLabel) {
            const name = document.createElement('div');
            name.className = 'sender-name';
            name.innerText = senderLabel;
            wrapper.appendChild(name);
        }

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        if (componentType !== 'chat') {
            bubble.classList.add('rich-content', `rich-${componentType}`);
        }
        bubble.appendChild(element);
        wrapper.appendChild(bubble);

        return wrapper;
    }
}
