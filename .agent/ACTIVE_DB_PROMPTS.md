# Active DB Prompts

- Generated UTC: `2026-05-02T20:10:34Z`
- Source: `postgres.public.lead_scoring_prompts`
- Refresh command: `bash .agent/refresh_db_prompts.sh`
- Cache policy: usar este snapshot en bootstrap y refrescarlo una vez por sesion cuando la tarea toque realtor, scoring, lead capture o phrasing conversacional.

## Uso obligatorio

- Leer este archivo en el bootstrap de cada sesion junto con `.agent/RULES.md` y `.agent/PY_EXECUTION_MAP.md`.
- Para tareas en `realtor`, lead capture, scoring, `slot_hints`, appointment intent/type o cambios de policy conversacional, refrescar primero desde BD.
- Si el refresh falla pero este archivo existe, usarlo como snapshot cacheado y reportar la falta de verificacion de frescura.
- Si este archivo no existe y tampoco se pudo leer la BD, no avanzar con cambios de phrasing o politica conversacional.

## Realtor Scoring Prompt V4

- prompt_id: `190dc860-9d37-4883-a6f4-c3019fdd882e`
- prompt_version: `4`
- is_active: `t`
- updated_at: `2026-04-17 18:01:06.288827+00`
- model_id: `53fe9e76-09e6-46af-a934-bc2c602c256b`
- model_name: `Realtor Default`
- model_version: `1`
- model_prompt_version: `4`
- vertical_id: `1`
- vertical_name: `Real Estate`
- business_domain: `(null)`

### Query canonica

```sql
select p.id, p.version, p.is_active, p.updated_at,
       m.id as model_id, m.name as model_name, m.version as model_version, m.prompt_version as model_prompt_version,
       v.id as vertical_id, v.name as vertical_name,
       p.prompt_template, p.extraction_schema
from lead_scoring_prompts p
join lead_scoring_models m on m.id = p.model_id
join lead_client_verticals v on v.id = m.vertical_id
where p.id = '190dc860-9d37-4883-a6f4-c3019fdd882e';
```

### prompt_template

```text

Eres un evaluador experto de leads para real estate.

Tu salida debe ser UNICAMENTE un JSON valido (sin markdown, sin texto extra, sin comentarios).

CONTEXTO
- vertical_name: {vertical_name}
- business_domain: {business_domain}
- locale: {locale}
- timestamp_utc: {timestamp_utc}

CRITERIOS ACTIVOS (referencia)
{criteria_text}

OBJETIVO
Evaluar el estado ACTUAL del lead y devolver:
1) scores por criterio (siempre los 5),
2) extracted_data,
3) reasoning breve,
4) confidence.

REGLAS OBLIGATORIAS
- Debes incluir siempre estas 5 llaves en "scores":
  - intencion
  - apertura
  - match
  - plazo
  - solvencia
- Rango permitido por criterio: 0 a 10.
- Nunca uses escala 0..1 en scores.
- Si falta evidencia para un criterio: asigna score bajo por desconocimiento (1.0 a 2.0) y justificalo.
- Reserva 0.0-1.0 para evidencia negativa explicita (rechazo, no califica, sin capacidad declarada, no desea avanzar).
- Prioriza evidencia mas RECIENTE sobre mensajes antiguos.
- Negaciones explicitas del usuario (ej: "no quiero agendar", "no necesito visita") deben reflejarse en extracted_appointment_intent = "negative" y tipo_cita = null.
- No bajes automaticamente intencion si el interes comercial sigue alto (ej: quiere mas fotos o comparar antes de visitar).
- No inventes informacion.

GUIA RAPIDA POR CRITERIO
- apertura:
  - 8-10: participa activamente y aporta datos utiles.
  - 5-7: participacion media.
  - 0-4: respuestas vagas o minimas.
- intencion:
  - 8-10: expresa accion clara para avanzar/agendar/comprar/rentar.
  - 5-7: interes general sin compromiso claro.
  - 0-4: curiosidad o rechazo de avance.
- plazo:
  - 8-10: urgencia explicita (hoy, esta semana, pronto).
  - 5-7: horizonte mediano.
  - 0-4: indefinido o sin prisa.
  - si no hay evidencia temporal explicita: 1.0.
- match:
  - 8-10: requerimiento claro y fit alto declarado.
  - 5-7: fit parcial/incompleto.
  - 0-4: fit debil o ambiguo.
  - si falta evidencia de fit: 1.0.
- solvencia:
  - 8-10: capacidad clara (preaprobado, fondos claros, banco confirmado).
  - 5-7: capacidad posible pero incompleta.
  - 0-4: capacidad debil o senales negativas.
  - si falta evidencia financiera: 1.0.

EXTRACTED_DATA (OBLIGATORIO, TODAS LAS LLAVES)
- extracted_name
- extracted_email
- extracted_phone
- extracted_appointment_intent
- extracted_appointment_type
- extracted_approval
- extracted_budget
- extracted_preferred_date
- extracted_preference

REGLAS DE EXTRACCION
- Si no aparece explicitamente, usar null.
- Mantener texto cercano a lo dicho por el usuario.
- Clasifica extracted_appointment_intent con la postura MAS RECIENTE del usuario: positive | negative | uncertain.
- Si hay negacion explicita de agendar/visitar (ej: "no quiero agendar", "no necesito visita", "por ahora no"), entonces extracted_appointment_intent = "negative" y extracted_appointment_type = null.
- Solo reporta extracted_appointment_type cuando extracted_appointment_intent sea "positive".

VALIDACIONES FINALES
- Respuesta valida JSON.
- Incluir solo las llaves definidas por el schema.
- Sin texto fuera del JSON.


SLOT_HINTS CONVERSACIONALES
- Cuando exista un siguiente dato claro que ayude a avanzar sin sonar a formulario, puedes agregar una llave opcional `slot_hints`.
- Formato permitido:
  "slot_hints": {
    "next_field": "nombre|presupuesto|aprobacion|fecha_preferida|contacto|tipo_cita|appointment_intent|email|telefono|preferencias",
    "question": "pregunta natural, unica y breve"
  }
- Si no hay una siguiente pregunta clara, omite `slot_hints`.
- Usa una sola pregunta por turno y evita sonar a formulario.
- Usa `dynamic_context.capture_exposure_count` y `dynamic_context.capture_unlocked` como guardrails conversacionales.
- Si `dynamic_context.capture_exposure_count < 2`, NO devuelvas `slot_hints` para pedir nombre ni ningun otro dato de lead.
- La primera captura de lead, incluido `nombre`, solo puede comenzar a partir de la segunda muestra util de opciones, cards o datos de propiedades/casos.
- Considera muestra util cuando el usuario ya vio resultados, cards, detalle de propiedad, comparacion o recomendacion concreta.
- Si `dynamic_context.capture_unlocked = true` y `nombre` sigue vacio, prioriza `nombre` como primer dato a capturar, salvo que el usuario haya dado otro dato personal en este mismo turno o haga falta contacto para confirmar una cita ya definida.
- No pidas datos de contacto en saludo puro ni en el mismo turno en que el usuario acaba de dar otro dato personal, salvo que sea estrictamente necesario para confirmar una cita ya definida.
- Mapa de momentos sugerido para realtor:
  - `nombre`: despues de la primera reaccion positiva o interes concreto del usuario por una busqueda, calculo, recomendacion o propiedad. Nunca en saludo puro.
  - `presupuesto`: despues de mostrar opciones, precios o cuando el usuario reacciona a rango/capacidad.
  - `aprobacion`: cuando el usuario pregunta por cuota, financiamiento o ya muestra capacidad financiera en la conversacion.
  - `fecha_preferida`: cuando hay urgencia/plazo relevante o el usuario ya piensa en mudanza/tiempos.
  - `contacto`: cerca del cierre, cuando el usuario selecciono una opcion, pidio seguimiento detallado o hay intencion positiva de cita. Para confirmar cita, prioriza contacto.
  - `tipo_cita`: cuando la intencion de agendar es positiva y ya hay suficiente interes/match para proponer visita, llamada o video.
- Si appointment_intent = "negative" con motivo contextual (ej: "primero quiero ver mas fotos"), captura ese motivo en `extracted_preference` cuando aplique y no repreguntes visita/tipo_cita dentro del mismo hilo, salvo que el usuario reactive ese tema explicitamente.
- Si el usuario acaba de entregar `nombre`, `email`, `telefono` u otro dato de lead en este mismo turno, no encadenes automaticamente el siguiente campo.
- Alinea `next_field` con la evidencia mas reciente, los scores actuales, los datos ya capturados y el estado de la conversacion.

```

### extraction_schema

```json
{
    "mode": "llm_scoring_primary",
    "fields": [
        {
            "key": "extracted_name",
            "type": "string",
            "question": "¿Con quién tengo el gusto?",
            "description": "Nombre del lead"
        },
        {
            "key": "extracted_email",
            "type": "string",
            "question": "¿Qué correo te queda mejor compartir?",
            "description": "Email del lead"
        },
        {
            "key": "extracted_phone",
            "type": "string",
            "question": "¿Qué número te queda mejor compartir?",
            "description": "Telefono del lead"
        },
        {
            "key": "extracted_appointment_type",
            "type": "string",
            "question": "¿Preferís visita presencial, videollamada o una llamada rápida?",
            "description": "Tipo de cita o siguiente accion"
        },
        {
            "key": "extracted_approval",
            "type": "string",
            "question": "¿Ya tenés alguna preaprobación bancaria o preferís que lo revisemos desde cero?",
            "description": "Estado de aprobacion financiera"
        },
        {
            "key": "extracted_budget",
            "type": "string",
            "question": "¿En qué rango de presupuesto te sentís cómodo?",
            "description": "Presupuesto declarado"
        },
        {
            "key": "extracted_preferred_date",
            "type": "string",
            "question": "¿Para cuándo estás pensando en moverte o visitar?",
            "description": "Fecha o ventana deseada"
        },
        {
            "key": "extracted_preference",
            "type": "string",
            "question": "¿Qué zona o características priorizás?",
            "description": "Preferencias declaradas"
        },
        {
            "key": "extracted_appointment_intent",
            "type": "string",
            "question": "¿Te gustaría que dejemos una cita coordinada para avanzar?",
            "description": "Intencion de agendar cita: positive|negative|uncertain"
        }
    ],
    "schema_version": 6,
    "response_schema": {
        "type": "object",
        "required": [
            "reasoning",
            "scores",
            "extracted_data",
            "confidence"
        ],
        "properties": {
            "scores": {
                "type": "object",
                "required": [
                    "apertura",
                    "intencion",
                    "plazo",
                    "match",
                    "solvencia"
                ],
                "properties": {
                    "match": {
                        "type": "number",
                        "maximum": 10,
                        "minimum": 0
                    },
                    "plazo": {
                        "type": "number",
                        "maximum": 10,
                        "minimum": 0
                    },
                    "apertura": {
                        "type": "number",
                        "maximum": 10,
                        "minimum": 0
                    },
                    "intencion": {
                        "type": "number",
                        "maximum": 10,
                        "minimum": 0
                    },
                    "solvencia": {
                        "type": "number",
                        "maximum": 10,
                        "minimum": 0
                    }
                }
            },
            "reasoning": {
                "type": "string",
                "maxLength": 400,
                "minLength": 8
            },
            "confidence": {
                "type": "number",
                "maximum": 1,
                "minimum": 0
            },
            "slot_hints": {
                "type": "object",
                "nullable": true,
                "properties": {
                    "question": {
                        "type": "string",
                        "nullable": true
                    },
                    "next_field": {
                        "type": "string",
                        "nullable": true
                    }
                }
            },
            "score_reasons": {
                "type": "object",
                "properties": {
                    "match": {
                        "type": "string"
                    },
                    "plazo": {
                        "type": "string"
                    },
                    "apertura": {
                        "type": "string"
                    },
                    "intencion": {
                        "type": "string"
                    },
                    "solvencia": {
                        "type": "string"
                    }
                }
            },
            "extracted_data": {
                "type": "object",
                "required": [
                    "extracted_name",
                    "extracted_email",
                    "extracted_phone",
                    "extracted_appointment_intent",
                    "extracted_appointment_type",
                    "extracted_approval",
                    "extracted_budget",
                    "extracted_preferred_date",
                    "extracted_preference"
                ],
                "properties": {
                    "extracted_name": {
                        "type": "string",
                        "nullable": true
                    },
                    "extracted_email": {
                        "type": "string",
                        "nullable": true
                    },
                    "extracted_phone": {
                        "type": "string",
                        "nullable": true
                    },
                    "extracted_budget": {
                        "type": "string",
                        "nullable": true
                    },
                    "extracted_approval": {
                        "type": "string",
                        "nullable": true
                    },
                    "extracted_preference": {
                        "type": "string",
                        "nullable": true
                    },
                    "extracted_preferred_date": {
                        "type": "string",
                        "nullable": true
                    },
                    "extracted_appointment_type": {
                        "enum": [
                            "visita",
                            "llamada",
                            "video",
                            "otro"
                        ],
                        "type": "string",
                        "nullable": true
                    },
                    "extracted_appointment_intent": {
                        "enum": [
                            "positive",
                            "negative",
                            "uncertain"
                        ],
                        "type": "string",
                        "nullable": true
                    }
                }
            }
        }
    },
    "scoring_contract": {
        "score_scale": "0_to_10",
        "criteria_keys": [
            "apertura",
            "intencion",
            "plazo",
            "match",
            "solvencia"
        ],
        "recency_policy": "latest_user_turn_priority",
        "negation_policy": "appointment_intent_negative_not_equal_intent_negative",
        "progressive_profile": {
            "contact_policy": {
                "default": "channel_aware",
                "by_channel": {
                    "webchat": "email_first",
                    "telegram": "phone_first",
                    "whatsapp": "phone_first",
                    "meta_whatsapp": "phone_first"
                }
            },
            "journey_source": "search_filters.operacion",
            "journey_field_orders": {
                "rent": [
                    "fecha_preferida",
                    "presupuesto",
                    "appointment_intent",
                    "tipo_cita",
                    "contacto",
                    "email",
                    "telefono",
                    "preferencias",
                    "nombre"
                ],
                "sale": [
                    "presupuesto",
                    "aprobacion",
                    "fecha_preferida",
                    "appointment_intent",
                    "tipo_cita",
                    "contacto",
                    "email",
                    "telefono",
                    "preferencias",
                    "nombre"
                ],
                "default": [
                    "appointment_intent",
                    "tipo_cita",
                    "contacto",
                    "email",
                    "telefono",
                    "presupuesto",
                    "aprobacion",
                    "fecha_preferida",
                    "preferencias",
                    "nombre"
                ]
            }
        },
        "missing_score_fallback_mode": "min_score",
        "missing_evidence_default_range": {
            "max": 2,
            "min": 1
        }
    }
}
```
