/**
 * REALTOR CHAT: POLYMORPHIC RENDERER CORE
 * Este es el cerebro del frontend. Recibe un JSON del Bridge y decide qué dibujar.
 */

export class ChatRenderer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.botName = "Hommie AI";
    }

    setBotName(name) {
        if (name) this.botName = name;
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
                const bubble = this.wrapInBubble(element, comp.sender || 'bot');
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
                el = document.createElement('property-card');
                el.title = config.title;
                el.price = config.price;
                el.location = config.location;
                el.imageUrl = config.image_url;
                el.publicUrl = config.public_url;
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

    wrapInBubble(element, sender) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${sender}`;

        const name = document.createElement('div');
        name.className = 'sender-name';
        name.innerText = sender === 'user' ? 'Tú' : this.botName;

        wrapper.appendChild(name);

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.appendChild(element);
        wrapper.appendChild(bubble);

        return wrapper;
    }
}
