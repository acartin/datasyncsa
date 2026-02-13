# 🎨 Manual de Branding Dinámico (SDUI Bridge)

Este documento define la jerarquía de diseño y las reglas de aplicación de color para el bot **Hommie AI**. Estas reglas aseguran la consistencia de marca y la accesibilidad (contraste) en todos los clientes/realtors.

## 🏛️ Jerarquía de Marca y Aplicación

| Variable de Color | Aplicación Específica en el Layout | Propósito de Diseño |
| :--- | :--- | :--- |
| **`primary_color`** | Fondos de jerarquía superior (Header/Cabecera), barras de navegación y contenedores de mensajes del bot. | Transmitir autoridad, confianza e identidad de marca. |
| **`text_on_primary`** | Texto, títulos e iconos que aparecen exclusivamente sobre el `primary_color`. | Garantizar legibilidad sobre la identidad principal. |
| **`secondary_color`** | Elementos de interacción y conversión (CTAs): Botones ("Ver Detalles", "Agendar Cita", etc.) e indicadores de estado activo. | Replicar la lógica de botones de la web principal para fomentar la conversión. |
| **`text_on_secondary`** | Texto o iconos que se muestran sobre los botones y acentos. | Asegurar el contraste según el color de énfasis del cliente. |
| **`surface_color`** | Fondo general de la ventana, tarjetas (cards) de propiedades y el área de entrada de texto (footer). | Proporcionar una base sólida y limpia para el contenido. |
| **`text_on_surface`** | Cuerpo del mensaje, descripciones técnicas, etiquetas de precios y el texto que el usuario escribe. | Maximizar el contraste y la legibilidad del contenido variable. |
| **`favicon_base64`** | Isotipo a color. | Pestaña del navegador (Tab). |
| **`logo_header_base64`** | Isotipo blanco. | Dentro del círculo del avatar del chat. |
| **`brand_wordmark_base64`** | Logotipo (Texto) blanco. | A la par del avatar en el header. |

## 🖋️ Configuración de Tipografías

| Elemento de UI | Variable de Fuente | Estilo Sugerido | Propósito |
| :--- | :--- | :--- | :--- |
| **Encabezados y Títulos** | `font_heading_name` | Bold (700) | Nombre del proyecto en header, títulos de casas y llamadas de atención principales. |
| **Cuerpo de Texto** | `font_body_name` | Regular (400) | Descripciones técnicas, mensajes del chat, precios y texto del usuario. |

## ✨ Estética y Acabados Premium

*   **Entorno Minimalista**: Se debe garantizar un entorno limpio utilizando el `surface_color` de fondo, evitando bordes pesados o ruidosos.
*   **Sombras y Bordes**: Se prefiere el uso de sombras sutiles configuradas en `box_shadow_style` y bordes redondeados definidos en `border_radius` (desde la DB) para dar profundidad y suavidad visual.
*   **Identidad vs Conversión**:
    *   `primary_color`: Identidad visual de la constructora (Estructura).
    *   `secondary_color`: Guía visual hacia la venta (CTAs/Interacción).

## 🛠️ Implementación Técnica (Variables CSS)

El sistema mapea automáticamente la respuesta del Bridge a las siguientes variables en el `:root`:

```css
:root {
    --brand-primary: [primary_color];
    --brand-secondary: [secondary_color];
    --brand-surface: [surface_color];
    
    --text-on-primary: [text_on_primary];
    --text-on-secondary: [text_on_secondary];
    --text-on-surface: [text_on_surface];

    --font-heading: [font_heading_name];
    --font-body: [font_body_name];
    --border-radius: [border_radius];
    --box-shadow: [box_shadow_style];
}
```

## ⚠️ Reglas de Oro
1.  **No usar colores fijos**: Ningún componente debe tener colores `hex` o `rgb` estáticos para elementos de marca. Siempre deben referenciar las variables anteriores.
2.  **Aislamiento de Superficie**: El `surface_color` debe usarse tanto para el fondo del chat como para el fondo de las tarjetas para mantener la simplicidad visual.
3.  **Prioridad de Conversión**: El `secondary_color` no debe usarse para elementos decorativos; está reservado para guiar al usuario hacia una acción (clic).
