# 🧠 Sistema de Scoring Inteligente - Lead Intelligence

## 📋 Resumen Ejecutivo

El sistema de scoring evalúa automáticamente la calidad de cada lead mediante 5 criterios independientes, calculados por IA a partir de conversaciones (chat/llamadas). Los scores se almacenan en PostgreSQL, donde triggers automáticos asignan iconografía, colores y clasificaciones desde un catálogo centralizado.

---

## 🎯 Criterios de Evaluación (100 puntos totales)

### 1. **Interés y Engagement** (30 pts)
Mide el nivel de compromiso e intención de compra del lead.

| Rango | Clasificación | Significado | Ejemplo |
|-------|--------------|-------------|---------|
| 24-30 | EXTREMO | Intención compra YA / Cita agendada | "Quiero verla mañana" |
| 18-23 | ALTO | Buscando activamente / Comparando | "Estoy viendo 3 opciones" |
| 12-17 | MODERADO | Interés informativo / Responde 3+ preguntas | "¿Cuánto cuesta?" |
| 6-11 | BAJO | Curioseando / Responde 1-2 preguntas | "Solo pregunto" |
| -20 a 5 | NULO | Rechazo explícito / Inactividad | "No me interesa" |

### 2. **Capacidad Financiera** (30 pts)
Evalúa si el lead puede costear la propiedad.

| Rango | Clasificación | Significado | Criterio |
|-------|--------------|-------------|----------|
| 30 | SOBRE-CALIFICADO | Puede pagar Cash o 2x budget | Ingresos > 2x precio |
| 25-29 | BIEN CALIFICADO | Ingresos cubren 40%+ del precio | Ratio deuda/ingreso favorable |
| 15-24 | CALIFICADO JUSTO | Ingresos cubren 30-40% | Necesita financiamiento |
| 5-14 | SUB-CALIFICADO | Ingresos cubren <30% | Riesgo crediticio |
| 0-4 | NO CALIFICADO | Sin ingresos o Deudas > Ingresos | No viable |
| -10 a -1 | EVASIVO | No dio info / Evade preguntas | Sospechoso |

### 3. **Timeline / Urgencia** (20 pts)
Determina qué tan pronto el lead quiere comprar.

| Rango | Clasificación | Timeframe |
|-------|--------------|-----------|
| 20 | INMEDIATO | Esta semana / Urgente |
| 18-19 | CALIENTE | Este mes |
| 15-17 | TIBIO | 1 a 3 meses |
| 10-14 | MEDIO PLAZO | 3 a 6 meses |
| 8-9 | INDEFINIDO | No sabe / Depende |
| 5-7 | LARGO PLAZO | 6 a 12 meses |
| 0-4 | FRÍO | +1 año / Solo viendo |

### 4. **Match con Inventario** (15 pts)
Evalúa si tenemos lo que el lead busca.

| Rango | Clasificación | Significado |
|-------|--------------|-------------|
| 13-15 | PERFECTO | Tenemos exactamente lo que busca |
| 10-12 | ALTO | Coincide en zona y presupuesto |
| 7-9 | MEDIO | Coincide solo en presupuesto |
| 4-6 | BAJO | Busca zona fuera de inventario |
| 0-3 | SIN COINCIDENCIA | Requerimientos no disponibles |

### 5. **Calidad de Información** (5 pts)
Mide la completitud y veracidad de los datos del lead.

| Rango | Clasificación | Significado |
|-------|--------------|-------------|
| 5 | ÍNTEGRO | Perfil completo y verificado |
| 3-4 | BUENO | Datos básicos verificados |
| 1-2 | INCOMPLETO | Falta email o teléfono |
| -3 a 0 | SOSPECHOSO | Datos falsos / Evasivo |

---

## 🏆 Clasificación de Prioridad (Score Total)

El score total (suma de los 5 criterios) determina la prioridad del lead:

| Score Total | Prioridad | Significado | Acción Recomendada |
|-------------|-----------|-------------|-------------------|
| 90-100 | **HOT** 🔥 | Cierre inminente / Cita agendada | Contacto inmediato |
| 70-89 | **WARM** 🌡️ | Interés sólido / En seguimiento activo | Seguimiento en 24h |
| 50-69 | **QUALIFIED** ✅ | Prospecto filtrado con éxito | Nutrir con contenido |
| 0-49 | **COLD** ❄️ | Seguimiento preventivo / Etapa inicial | Campaña automatizada |

---

## 🔄 Flujo Técnico del Sistema

### **Paso 1: IA Evalúa la Conversación**
```
Lead conversa por WhatsApp/Chat/Llamada
    ↓
IA analiza el contenido (GPT-4, Claude, etc.)
    ↓
IA asigna los 5 scores individuales
```

**Ejemplo de Output de IA:**
```json
{
  "score_engagement": 28,
  "score_finance": 26,
  "score_timeline": 20,
  "score_match": 14,
  "score_info": 5
}
```

### **Paso 2: Inserción en Base de Datos**
```sql
INSERT INTO lead_leads (
    client_id,
    full_name,
    email,
    phone,
    declared_income,
    current_debts,
    score_engagement,  -- ← IA asigna 28
    score_finance,     -- ← IA asigna 26
    score_timeline,    -- ← IA asigna 20
    score_match,       -- ← IA asigna 14
    score_info,        -- ← IA asigna 5
    source_property_ref,
    source_property_url,
    estimated_value,
    property_snapshot
) VALUES (
    '019b4872-51f6-72d3-84c9-45183ff700d0',
    'Carlos Méndez',
    'carlos@example.com',
    '+1-555-1001',
    120000.00,
    5000.00,
    28, 26, 20, 14, 5,
    'wp-12345',
    'https://inmobiliaria.com/casa-playa',
    350000.00,
    '{"title": "Casa Playa", "bedrooms": 3}'
);
```

### **Paso 3: Trigger Automático de PostgreSQL**
Al insertar/actualizar un lead, el trigger `fn_calculate_lead_score()` se ejecuta automáticamente:

```sql
CREATE OR REPLACE FUNCTION fn_calculate_lead_score() RETURNS TRIGGER AS $$
BEGIN
    -- 1. Calcula el Score Total (suma de los 5 criterios)
    NEW.score_total := GREATEST(0, LEAST(100, 
        COALESCE(NEW.score_engagement, 0) + 
        COALESCE(NEW.score_finance, 0) + 
        COALESCE(NEW.score_timeline, 0) + 
        COALESCE(NEW.score_match, 0) + 
        COALESCE(NEW.score_info, 0)
    ));
    -- Resultado: 28 + 26 + 20 + 14 + 5 = 93

    -- 2. Busca las definiciones en el catálogo
    NEW.eng_def_id := (
        SELECT id FROM lead_scoring_definitions 
        WHERE criterion = 'engagement' 
        AND NEW.score_engagement BETWEEN min_score AND max_score 
        LIMIT 1
    );
    -- Para score_engagement = 28 → encuentra "EXTREMO" (24-30)
    
    NEW.fin_def_id := (...);      -- Para finance
    NEW.timeline_def_id := (...); -- Para timeline
    NEW.match_def_id := (...);    -- Para match
    NEW.info_def_id := (...);     -- Para info
    NEW.priority_def_id := (...); -- Para prioridad total (93 → HOT)

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### **Paso 4: UI Lee las Relaciones**
```php
// En el modelo Lead.php
public function engagementDef() { 
    return $this->belongsTo(ScoringDefinition::class, 'eng_def_id'); 
}

// En la vista Blade
$lead->engagementDef->icon   // → "message-square-heart"
$lead->engagementDef->color  // → "thermal-extreme"
$lead->engagementDef->meaning // → "Intención compra YA / Cita agendada"
```

---

## 🗄️ Estructura de Base de Datos

### **Tabla: `lead_leads`**
```sql
CREATE TABLE lead_leads (
    id UUID PRIMARY KEY,
    client_id UUID NOT NULL,
    full_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(255),
    
    -- Scores individuales (asignados por IA)
    score_engagement INTEGER,
    score_finance INTEGER,
    score_timeline INTEGER,
    score_match INTEGER,
    score_info INTEGER,
    score_total INTEGER, -- ← Calculado por trigger
    
    -- Referencias a definiciones (asignadas por trigger)
    eng_def_id BIGINT REFERENCES lead_scoring_definitions(id),
    fin_def_id BIGINT REFERENCES lead_scoring_definitions(id),
    timeline_def_id BIGINT REFERENCES lead_scoring_definitions(id),
    match_def_id BIGINT REFERENCES lead_scoring_definitions(id),
    info_def_id BIGINT REFERENCES lead_scoring_definitions(id),
    priority_def_id BIGINT REFERENCES lead_scoring_definitions(id),
    
    -- Property tracking
    source_property_ref VARCHAR(255),
    source_property_url TEXT,
    estimated_value DECIMAL(15,2),
    property_snapshot JSONB,
    
    created_at TIMESTAMP,
    deleted_at TIMESTAMP
);
```

### **Tabla: `lead_scoring_definitions`** (Catálogo)
```sql
CREATE TABLE lead_scoring_definitions (
    id BIGSERIAL PRIMARY KEY,
    criterion VARCHAR(50),  -- 'engagement', 'finance', 'timeline', etc.
    min_score INTEGER,
    max_score INTEGER,
    label VARCHAR(100),     -- 'EXTREMO', 'ALTO', etc.
    meaning TEXT,           -- Descripción cualitativa
    icon VARCHAR(100),      -- Nombre del icono (Lucide)
    color VARCHAR(50),      -- Clase CSS térmica
    is_active BOOLEAN
);
```

**Ejemplo de registros:**
| id | criterion | min_score | max_score | label | meaning | icon | color |
|----|-----------|-----------|-----------|-------|---------|------|-------|
| 1 | engagement | 24 | 30 | EXTREMO | Intención compra YA | message-square-heart | thermal-extreme |
| 7 | finance | 25 | 29 | BIEN CALIFICADO | Ingresos cubren 40%+ | landmark | thermal-finance-high |
| 13 | timeline | 20 | 20 | INMEDIATO | Esta semana | clock | t-inmediato |
| 30 | priority | 90 | 100 | HOT | Cierre inminente | gauge | thermal-extreme |

---

## 🎨 Sistema de Colores Térmicos

Los colores se definen centralmente en `AppPanelProvider.php`:

```css
/* Escala de Engagement/Match/Info */
.thermal-extreme { color: #ef4444 !important; } /* Rojo brillante */
.thermal-high { color: #f97316 !important; }    /* Naranja */
.thermal-mid { color: #f59e0b !important; }     /* Ámbar */
.thermal-low { color: #eab308 !important; }     /* Amarillo */
.thermal-none { color: #475569 !important; }    /* Gris */

/* Escala de Finance (Emerald) */
.thermal-finance-extreme { color: #34d399 !important; }
.thermal-finance-high { color: #10b981 !important; }

/* Escala de Timeline */
.t-inmediato { color: #ef4444 !important; }
.t-caliente { color: #f87171 !important; }
.t-tibio { color: #fb923c !important; }
.t-medio { color: #fbbf24 !important; }
.t-indefinido { color: #3b82f6 !important; }
.t-largo { color: #94a3b8 !important; }
.t-frio { color: #475569 !important; }
```

---

## 📊 Ejemplo Completo de Lead

### **Input (desde IA):**
```json
{
  "full_name": "Carlos Méndez",
  "email": "carlos@example.com",
  "phone": "+1-555-1001",
  "declared_income": 120000,
  "current_debts": 5000,
  "source_property_ref": "wp-12345",
  "source_property_url": "https://inmobiliaria.com/casa-playa",
  "estimated_value": 350000,
  "property_snapshot": {
    "title": "Casa Playa Premium",
    "bedrooms": 3,
    "bathrooms": 2
  },
  "scores": {
    "engagement": 28,
    "finance": 26,
    "timeline": 20,
    "match": 14,
    "info": 5
  }
}
```

### **Procesamiento Automático:**
1. **Trigger calcula:** `score_total = 93`
2. **Trigger asigna definiciones:**
   - `eng_def_id` → ID 1 (EXTREMO)
   - `fin_def_id` → ID 7 (BIEN CALIFICADO)
   - `timeline_def_id` → ID 13 (INMEDIATO)
   - `match_def_id` → ID 17 (PERFECTO)
   - `info_def_id` → ID 21 (ÍNTEGRO)
   - `priority_def_id` → ID 30 (HOT)

### **Output en UI:**
```
┌─────────────────────────────────────┐
│  🔥 CARLOS MÉNDEZ          Score: 93│
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                     │
│  💬 Intención compra YA        28   │
│  🏛️ Ingresos cubren 40%+      26   │
│  ⏰ Esta semana               20   │
│  🏠 Tenemos lo que busca      14   │
│  📝 Perfil completo            5   │
│                                     │
│  🏡 Casa Playa Premium              │
│  💰 $350,000                        │
│  🔗 Ver Propiedad                   │
└─────────────────────────────────────┘
```

---

## 🚀 Integración con IA

### **Endpoint Sugerido:**
```php
// POST /api/leads/from-conversation
Route::post('/leads/from-conversation', function (Request $request) {
    $aiScores = $request->input('scores'); // De GPT-4/Claude
    
    $lead = Lead::create([
        'client_id' => $request->input('client_id'),
        'full_name' => $request->input('full_name'),
        'email' => $request->input('email'),
        'phone' => $request->input('phone'),
        'declared_income' => $request->input('declared_income'),
        'current_debts' => $request->input('current_debts'),
        
        // Scores de IA
        'score_engagement' => $aiScores['engagement'],
        'score_finance' => $aiScores['finance'],
        'score_timeline' => $aiScores['timeline'],
        'score_match' => $aiScores['match'],
        'score_info' => $aiScores['info'],
        
        // Property tracking
        'source_property_ref' => $request->input('property_ref'),
        'source_property_url' => $request->input('property_url'),
        'estimated_value' => $request->input('property_value'),
        'property_snapshot' => $request->input('property_snapshot'),
    ]);
    
    // El trigger ya calculó score_total y asignó los *_def_id
    
    return response()->json([
        'lead_id' => $lead->id,
        'score_total' => $lead->score_total,
        'priority' => $lead->priorityDef->label, // "HOT"
    ]);
});
```

---

## 📝 Notas Importantes

1. **Los scores individuales SIEMPRE vienen de la IA** - No se calculan en la base de datos.
2. **El trigger solo calcula el total y asigna definiciones** - No modifica los scores individuales.
3. **El catálogo es configurable** - Puedes ajustar rangos, iconos y colores sin tocar código.
4. **Property tracking es opcional** - Si no hay propiedad asociada, esos campos pueden ser NULL.
5. **El sistema es 100% database-driven** - Cambios en `lead_scoring_definitions` se reflejan instantáneamente en la UI.

---

## 🔧 Mantenimiento

### **Ajustar Rangos de Scoring:**
```sql
UPDATE lead_scoring_definitions
SET min_score = 25, max_score = 30
WHERE criterion = 'engagement' AND label = 'EXTREMO';
```

### **Cambiar Iconografía:**
```sql
UPDATE lead_scoring_definitions
SET icon = 'zap', color = 'thermal-extreme'
WHERE criterion = 'engagement' AND label = 'EXTREMO';
```

### **Recalcular Leads Existentes:**
```sql
UPDATE lead_leads SET score_total = score_total;
-- Esto dispara el trigger y reasigna las definiciones
```

--- Estatus e Intención
Las columnas Status(workflow) e Intención (Outcome) en el panel de leads tienen objetivos distintos para clasificar el estado y la intención de cada prospecto:

1. Estatus (Estado Operacional)
Esta columna representa la etapa del ciclo de vida del lead dentro de tu proceso comercial. Responde a la pregunta: ¿En qué punto de nuestro proceso interno se encuentra este lead?

Mapeo técnico: Está vinculada al modelo LeadStatus (definido en 
LeadStatus.php). Y es inicializada en la bd

Valores comunes: "New" (Nuevo), "Contacted" (Contactado), "Qualified" (Calificado), "Won" (Ganado) o "Lost" (Perdido).
Objetivo: Gestionar la operación diaria y saber qué leads requieren atención según su progreso en el embudo de ventas.

Esencialmente es el estatus del lead en el embudo de ventas.

2. Outcome (Intención / Resultado de Interacción)
Dato generado por la IA en el momento de la creación del lead.
Esta columna identifica el objetivo final o el interés determinado tras la interacción inicial Responde a la pregunta: ¿Qué es lo que el lead quiere o cuál fue el resultado de la conversación?

Mapeo técnico: Está vinculada a la tabla lead_contact_preferences (definido en 
ContactPreference.php
).
Valores comunes: "Meeting Pending" (Cita pendiente), "Voice Call" (Llamada de voz), "Chat / Messenger", "Email info", etc.
Objetivo: Clasificar el resultado de la interacción. Mientras que el Workflow te dice que el lead está "Calificado", el Outcome te especifica que ese lead calificado está esperando una "Llamada de voz" o una "Cita".
En resumen: Workflow es el estado de tu proceso interno, mientras que Outcome es la intención o el paso siguiente solicitado por el lead.


Intención: El Bot lo setea en la bd como  basándose en el análisis de la conversación (IA). Si el lead pidió una llamada, el bot lo marcará como "Voice Call"; si agendó una cita, como "Meeting Pending", etc.
2. Cambios de Estado (Evolución)
Una vez que el lead ya está en el sistema, la responsabilidad recae principalmente en el Agente Humano (Vendedor/Admin):

Estado: El Agente cambia este estado manualmente a medida que avanza en su gestión (pasándolo de "New" a "Contacted", "Qualified", "Won" o "Lost"). Es la herramienta del vendedor para medir su progreso.
Intención: Aunque el Bot lo setea al inicio, el Agente puede cambiarlo si durante el seguimiento descubre que el lead prefiere otra vía (por ejemplo, el lead pidió chat, pero luego de hablar prefiere una "Video Call").
