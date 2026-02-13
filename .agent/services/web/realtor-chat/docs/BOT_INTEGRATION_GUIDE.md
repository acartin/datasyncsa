# 🤖 Guía de Integración del Bot con Lead Intelligence

## 📊 Resumen

Esta guía explica cómo el bot debe insertar leads y conversaciones en la base de datos después de calificar a un prospecto.

---

## 🔄 Flujo Completo

```
1. Usuario hace click en anuncio (Meta/Google/QR)
   ↓
2. Bot recibe contacto con UTM parameters
   ↓
3. Bot conversa y califica (IA genera scores)
   ↓
4. AI Processing: El Bot genera el **Resumen Ejecutivo** y **Análisis de Sentimiento**
   ↓
5. Bot inserta Lead + Conversación en BD
```

---

## 🤖 Procesamiento de IA (Responsabilidad del Bot)

Antes de realizar la inserción en la base de datos, el Bot debe procesar el historial de la conversación para extraer:

1.  **Resumen Ejecutivo (`summary`):** Un extracto de 2-3 líneas que resuma el interés, presupuesto y urgencia del lead.
2.  **Análisis de Sentimiento (`sentiment`):** Clasificación de la actitud del lead (`positive`, `neutral`, `negative`).
3.  **Calificación (`scores`):** Evaluación de los 5 pilares de Lead Intelligence.

---

## 💻 Ejemplo de Código PHP (desde el Bot)

### **Paso 1: Preparar Datos del Lead**

```php
use App\Models\Lead;
use App\Models\Conversation;

// Datos capturados del link UTM
$utmParams = [
    'utm_source' => 'facebook',
    'utm_medium' => 'paid',
    'utm_campaign' => 'casas-premium-2026',
    'utm_content' => 'carousel-ad-v2',
    'utm_term' => null,
];

// Click ID de la plataforma
$clickId = 'fbclid_IwAR123xyz';

// Datos de la sesión
$sessionData = [
    'referrer_url' => 'https://facebook.com/ads/...',
    'landing_page_url' => 'https://inmobiliaria.com/propiedad/casa-playa?utm_source=facebook&...',
    'user_agent' => 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)...',
    'ip_address' => '192.168.1.100',
];

// Datos de la propiedad
$propertyData = [
    'source_property_ref' => 'wp-12345',
    'source_property_url' => 'https://inmobiliaria.com/propiedad/casa-playa',
    'estimated_value' => 350000.00,
    'property_snapshot' => [
        'title' => 'Casa Playa Premium',
        'bedrooms' => 3,
        'bathrooms' => 2,
        'area_sqm' => 150,
    ],
];

// Scores calculados por IA
$scores = [
    'score_engagement' => 28,  // IA evaluó la conversación
    'score_finance' => 26,
    'score_timeline' => 20,
    'score_match' => 14,
    'score_info' => 5,
];

// Datos del lead
$leadData = [
    'full_name' => 'Carlos Méndez',
    'email' => 'carlos@example.com',
    'phone' => '+1-555-1001',
    'declared_income' => 120000.00,
    'current_debts' => 5000.00,
];
```

### **Paso 2: Insertar Lead en la BD**

```php
$lead = Lead::create([
    // Relaciones
    'client_id' => '019b4872-51f6-72d3-84c9-45183ff700d0', // ID del cliente (inmobiliaria)
    'source_id' => 3, // Facebook Ads (de la tabla lead_sources)
    'status_id' => 1, // Nuevo (de la tabla lead_statuses)
    
    // Datos del lead
    'full_name' => $leadData['full_name'],
    'email' => $leadData['email'],
    'phone' => $leadData['phone'],
    'declared_income' => $leadData['declared_income'],
    'current_debts' => $leadData['current_debts'],
    'financial_currency_id' => 'USD',
    
    // Scores (calculados por IA)
    'score_engagement' => $scores['score_engagement'],
    'score_finance' => $scores['score_finance'],
    'score_timeline' => $scores['score_timeline'],
    'score_match' => $scores['score_match'],
    'score_info' => $scores['score_info'],
    // score_total se calcula automáticamente por trigger
    
    // Property tracking
    'source_property_ref' => $propertyData['source_property_ref'],
    'source_property_url' => $propertyData['source_property_url'],
    'estimated_value' => $propertyData['estimated_value'],
    'property_snapshot' => $propertyData['property_snapshot'],
    
    // UTM tracking
    'utm_source' => $utmParams['utm_source'],
    'utm_medium' => $utmParams['utm_medium'],
    'utm_campaign' => $utmParams['utm_campaign'],
    'utm_content' => $utmParams['utm_content'],
    'utm_term' => $utmParams['utm_term'],
    
    // Click ID
    'click_id' => $clickId,
    'click_id_type' => 'fbclid',
    
    // Session metadata
    'referrer_url' => $sessionData['referrer_url'],
    'landing_page_url' => $sessionData['landing_page_url'],
    'user_agent' => $sessionData['user_agent'],
    'ip_address' => $sessionData['ip_address'],
]);
```

### **Paso 3: Insertar Conversación**

```php
// Mensajes de la conversación (capturados durante el chat)
$messages = [
    [
        'timestamp' => '2026-01-03T01:00:00Z',
        'sender' => 'bot',
        'text' => '¡Hola! Vi que te interesa la Casa Playa Premium. ¿En qué puedo ayudarte?',
        'type' => 'text',
    ],
    [
        'timestamp' => '2026-01-03T01:00:30Z',
        'sender' => 'lead',
        'text' => 'Hola, quiero saber el precio',
        'type' => 'text',
    ],
    [
        'timestamp' => '2026-01-03T01:00:45Z',
        'sender' => 'bot',
        'text' => 'La propiedad tiene un valor de $350,000. ¿Cuál es tu presupuesto aproximado?',
        'type' => 'text',
    ],
    [
        'timestamp' => '2026-01-03T01:01:15Z',
        'sender' => 'lead',
        'text' => 'Tengo hasta $400,000',
        'type' => 'text',
    ],
    [
        'timestamp' => '2026-01-03T01:01:30Z',
        'sender' => 'bot',
        'text' => 'Perfecto, estás bien calificado. ¿Cuándo te gustaría verla?',
        'type' => 'text',
    ],
    [
        'timestamp' => '2026-01-03T01:02:00Z',
        'sender' => 'lead',
        'text' => 'Esta semana si es posible',
        'type' => 'text',
    ],
];

$conversation = Conversation::create([
    'lead_id' => $lead->id,
    'platform' => 'webchat',
    'conversation_id' => 'session_xyz_789', // ID de sesión de tu bot local
    'messages' => $messages,
    'summary' => 'Lead interesado en Casa Playa Premium. Presupuesto $400K. Quiere visita esta semana.',
    'sentiment' => 'positive',
    'started_at' => '2026-01-03T01:00:00Z',
    'ended_at' => '2026-01-03T01:02:30Z',
    'total_messages' => count($messages),
    'bot_messages' => 3,
    'lead_messages' => 3,
]);
```

---

## 🎯 Resultado en la Base de Datos

### **Tabla `lead_leads`:**
```
id: 019b8110-1d83-70d2-95b5-ae97f8761856
client_id: 019b4872-51f6-72d3-84c9-45183ff700d0
full_name: Carlos Méndez
email: carlos@example.com
phone: +1-555-1001
score_total: 93 (calculado por trigger)
utm_source: facebook
utm_campaign: casas-premium-2026
click_id: fbclid_IwAR123xyz
source_property_ref: wp-12345
estimated_value: 350000.00
```

### **Tabla `lead_conversations`:**
```
id: 019b8110-1d83-70d2-95b5-ae97f8761857
lead_id: 019b8110-1d83-70d2-95b5-ae97f8761856
platform: webchat
messages: [6 mensajes en JSONB]
summary: "Lead interesado en Casa Playa Premium..."
sentiment: positive
total_messages: 6
```

---

## 🔍 Consultas Útiles

### **Ver lead con su conversación:**
```php
$lead = Lead::with('conversations')->find($leadId);
$conversation = $lead->conversations->first();
$messages = $conversation->messages;
```

### **Buscar leads por campaña:**
```php
$leads = Lead::where('utm_campaign', 'casas-premium-2026')->get();
```

### **Buscar en mensajes (JSONB):**
```sql
SELECT * FROM lead_conversations 
WHERE messages @> '[{"sender": "lead", "text": "urgente"}]';
```

### **ROI por campaña:**
```php
$roi = Lead::select('utm_campaign')
    ->selectRaw('COUNT(*) as total_leads')
    ->selectRaw('SUM(estimated_value) as potential_revenue')
    ->selectRaw('AVG(score_total) as avg_quality')
    ->where('utm_source', 'facebook')
    ->groupBy('utm_campaign')
    ->get();
```

---

## 📝 Notas Importantes

1. **El trigger calcula automáticamente:**
   - `score_total` (suma de los 5 scores)
   - `eng_def_id`, `fin_def_id`, etc. (referencias a definiciones)

2. **No necesitas insertar:**
   - `created_at`, `updated_at` (automáticos)
   - `score_total` (calculado por trigger)
   - `*_def_id` (asignados por trigger)

3. **Campos opcionales:**
   - `utm_*` (si no vienen de un link con UTM)
   - `click_id` (si no es de plataforma publicitaria)
   - `property_snapshot` (si no hay propiedad asociada)

4. **Validaciones:**
   - `platform` debe ser: 'webchat', 'telegram', 'messenger', 'instagram', 'whatsapp' (opcional)
   - `sentiment` debe ser: 'positive', 'neutral', 'negative' o NULL

---

**Última actualización:** 2026-01-03  
**Versión:** 1.0
