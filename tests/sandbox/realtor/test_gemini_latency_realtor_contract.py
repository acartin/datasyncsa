"""
Benchmark de latencia Gemini para scoring con contrato JSON (sandbox).

Base de conversaciones:
- Escenarios inspirados en `tests/sandbox/realtor/simulate_multichat_realtor.py`

Uso:
  RUN_GEMINI_BENCH=1 python3 -m pytest -q tests/sandbox/realtor/test_gemini_latency_realtor_contract.py -s

Opcionales:
  GEMINI_BENCH_REPEATS=3
  GEMINI_BENCH_MODEL=gemini-2.0-flash
  GEMINI_LATENCY_MAX_SECS=12
  GEMINI_BENCH_SCENARIOS=1,5
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pytest

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


@dataclass(frozen=True)
class Scenario:
    scenario_id: int
    name: str
    description: str
    messages: List[str]
    expected_appointment_intent: str


# Escenarios tomados de simulate_multichat_realtor.py (misma narrativa y textos).
SCENARIOS: Dict[int, Scenario] = {
    1: Scenario(
        scenario_id=1,
        name="comprador_caliente_preaprobado",
        description="Alta intencion, timeline corto, presupuesto claro y preaprobacion.",
        messages=[
            "Hola, vi una casa en Heredia y me interesa comprar pronto.",
            "Me llamo Ana Vargas, mi correo es ana.vargas@gmail.com y mi telefono 8899-1122.",
            "Tenemos preaprobacion bancaria con BAC y presupuesto entre 125 mil y 145 mil dolares.",
            "Queremos agendar visita esta misma semana, idealmente jueves en la tarde.",
        ],
        expected_appointment_intent="wants_schedule",
    ),
    2: Scenario(
        scenario_id=2,
        name="exploratorio_sin_urgencia",
        description="Interes bajo/medio, sin urgencia ni datos financieros concretos.",
        messages=[
            "Hola, solo estoy viendo opciones por ahora.",
            "Tal vez me mude el proximo ano, aun no tengo fecha definida.",
            "No tengo preaprobacion ni presupuesto cerrado todavia.",
            "Solo queria saber en que zonas de Alajuela hay casas familiares.",
        ],
        expected_appointment_intent="not_wants_schedule",
    ),
    3: Scenario(
        scenario_id=3,
        name="familia_timeline_medio",
        description="Familia con requerimientos claros y contacto completo, sin financiamiento aprobado.",
        messages=[
            "Busco apartamento en Escazu con 2 o 3 habitaciones y parqueo.",
            "Soy Carlos Mena, correo carlos.mena@correo.com, telefono 8777-3344.",
            "Nuestro presupuesto ronda los 95 mil dolares pero aun no tenemos preaprobacion.",
            "Nos gustaria mudarnos en unos 4 a 6 meses.",
        ],
        expected_appointment_intent="undecided",
    ),
    4: Scenario(
        scenario_id=4,
        name="inversionista_contado_urgente",
        description="Lead inversionista, alta capacidad financiera y alta urgencia.",
        messages=[
            "Buenas, busco propiedad para inversion en Heredia centro.",
            "Tengo fondos al contado por 200 mil dolares.",
            "Mi nombre es Laura Campos y mi correo es laura.campos@capital.cr.",
            "Si encaja, quiero visitar manana en la manana.",
        ],
        expected_appointment_intent="wants_schedule",
    ),
    5: Scenario(
        scenario_id=5,
        name="curioso_baja_conversion",
        description="Conversacion corta con poca informacion util y baja intencion de avance.",
        messages=[
            "Hola, vi un anuncio y queria saber el precio nada mas.",
            "Estoy comparando por curiosidad, aun no pienso moverme.",
            "No tengo presupuesto definido ni fecha, luego les escribo.",
            "Gracias, por ahora no necesito agendar visita.",
        ],
        expected_appointment_intent="not_wants_schedule",
    ),
}


def _selected_scenarios() -> List[Scenario]:
    raw = (os.getenv("GEMINI_BENCH_SCENARIOS") or "").strip()
    if not raw:
        return [SCENARIOS[i] for i in sorted(SCENARIOS.keys())]

    selected: List[Scenario] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        scenario_id = int(token)
        if scenario_id not in SCENARIOS:
            raise ValueError(f"Escenario invalido en GEMINI_BENCH_SCENARIOS: {scenario_id}")
        selected.append(SCENARIOS[scenario_id])
    return selected


def _build_transcript(messages: List[str], include_assistant_turns: bool = True) -> str:
    lines: List[str] = []
    for msg in messages:
        lines.append(f"Usuario: {msg}")
        if include_assistant_turns:
            lines.append(
                "Asistente: Gracias por el contexto. "
                "¿Me puedes compartir presupuesto, fecha objetivo y si deseas agendar visita?"
            )
    return "\n".join(lines)


def _response_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "appointment_intent": {
                "type": "string",
                "enum": ["wants_schedule", "not_wants_schedule", "undecided"],
            },
            "scores": {
                "type": "object",
                "properties": {
                    "intent": {"type": "number", "minimum": 0.0, "maximum": 10.0},
                    "engagement": {"type": "number", "minimum": 0.0, "maximum": 10.0},
                    "timeline": {"type": "number", "minimum": 0.0, "maximum": 10.0},
                    "match": {"type": "number", "minimum": 0.0, "maximum": 10.0},
                    "finance": {"type": "number", "minimum": 0.0, "maximum": 10.0},
                },
                "required": ["intent", "engagement", "timeline", "match", "finance"],
            },
            "extracted_data": {
                "type": "object",
                "properties": {
                    "extracted_name": {"type": "string", "nullable": True},
                    "extracted_email": {"type": "string", "nullable": True},
                    "extracted_phone": {"type": "string", "nullable": True},
                    "extracted_budget": {"type": "string", "nullable": True},
                    "extracted_approval": {"type": "string", "nullable": True},
                    "extracted_preferred_date": {"type": "string", "nullable": True},
                    "extracted_preference": {"type": "string", "nullable": True},
                    "extracted_appointment_type": {"type": "string", "nullable": True},
                },
            },
            "contradictions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["reasoning", "confidence", "appointment_intent", "scores", "extracted_data"],
    }


def _short_system_prompt() -> str:
    return (
        "Eres un evaluador semantico de leads inmobiliarios.\n"
        "Responde SOLO JSON valido.\n"
        "Reglas:\n"
        "- Prioriza semantica sobre keywords.\n"
        "- Si el usuario dice que NO quiere agendar, appointment_intent='not_wants_schedule'.\n"
        "- Si hay conflicto entre mensajes, prioriza el mensaje mas reciente del usuario.\n"
        "- No inventes datos no expresados.\n"
    )


def _long_system_prompt() -> str:
    return (
        "Eres un evaluador experto de leads para real estate.\n"
        "Tu salida debe ser UNICAMENTE un JSON valido.\n"
        "OBJETIVO: analizar la conversacion y devolver scores, extracted_data, reasoning y confidence.\n"
        "REGLAS OBLIGATORIAS DE SCORING:\n"
        "- Debes incluir SIEMPRE engagement, intent, timeline, match, finance.\n"
        "- Si falta evidencia para un criterio, asigna score conservador 4.0 a 5.0.\n"
        "- Rango permitido por criterio: 0 a 10.\n"
        "GUIA POR CRITERIO:\n"
        "- engagement: 8-10 datos utiles y conversacion activa; 5-7 parcial; 0-4 vago.\n"
        "- intent: 8-10 intencion clara de agendar/avanzar; 5-7 interes general; 0-4 curiosidad.\n"
        "- timeline: 8-10 urgencia explicita; 5-7 meses; 0-4 indefinido; sin evidencia usar 5.0.\n"
        "- match: evaluar fit de requerimientos declarados; sin evidencia usar 5.0.\n"
        "- finance: 8-10 capacidad fuerte; 5-7 incompleta; 0-4 debil; sin evidencia usar 5.0.\n"
        "EXTRACCION OBLIGATORIA EN extracted_data:\n"
        "- extracted_name, extracted_email, extracted_phone, extracted_appointment_type,\n"
        "  extracted_approval, extracted_budget, extracted_preferred_date, extracted_preference.\n"
        "REGLAS DE EXTRACCION: si no aparece explicito usa null. No inventar.\n"
        "VALIDACIONES FINALES:\n"
        "- JSON valido.\n"
        "- scores con exactamente 5 llaves.\n"
        "- extracted_data con todas las llaves requeridas.\n"
    )


def _prompt_variants(mode: str) -> List[Tuple[str, str]]:
    normalized = (mode or "both").strip().lower()
    if normalized == "short":
        return [("short", _short_system_prompt())]
    if normalized == "long":
        return [("long", _long_system_prompt())]
    return [
        ("short", _short_system_prompt()),
        ("long", _long_system_prompt()),
    ]


def _quality_flags(payload: Dict[str, Any], expected_intent: str) -> Dict[str, bool]:
    scores = payload.get("scores") or {}
    values = []
    if isinstance(scores, dict):
        for key in ("engagement", "intent", "timeline", "match", "finance"):
            try:
                values.append(float(scores.get(key)))
            except Exception:
                values.append(-1.0)
    model_intent = str(payload.get("appointment_intent") or "").strip()
    all_scores_leq_one = bool(values) and all(v <= 1.0 for v in values)
    return {
        "intent_ok": model_intent == expected_intent,
        "scale_looks_0_10": not all_scores_leq_one,
    }


def _p95(values: List[float]) -> float:
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=20, method="inclusive")[18]


async def _call_gemini(
    *,
    client: Any,
    model: str,
    system_prompt: str,
    transcript: str,
    response_schema: Dict[str, Any],
) -> Dict[str, Any]:
    from google.genai import types

    prompt = "Analiza esta conversacion de messenger y devuelve solo el JSON del contrato.\n\n" + transcript

    started = time.perf_counter()
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )
    llm_ms = (time.perf_counter() - started) * 1000.0

    raw = response.text or ""
    parse_started = time.perf_counter()
    payload = json.loads(raw)
    parse_ms = (time.perf_counter() - parse_started) * 1000.0

    return {
        "llm_ms": llm_ms,
        "parse_ms": parse_ms,
        "total_ms": llm_ms + parse_ms,
        "response_chars": len(raw),
        "payload": payload,
    }


@pytest.mark.asyncio
async def test_gemini_latency_realtor_contract_sandbox():
    if load_dotenv:
        load_dotenv()

    if os.getenv("RUN_GEMINI_BENCH", "0") != "1":
        pytest.skip("Set RUN_GEMINI_BENCH=1 para ejecutar benchmark real de Gemini.")

    api_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        pytest.skip("GOOGLE_API_KEY no esta configurado.")

    try:
        from google import genai
    except Exception as exc:  # pragma: no cover - depends on local env
        pytest.skip(f"google-genai no disponible: {exc}")

    model = os.getenv("GEMINI_BENCH_MODEL", "gemini-2.0-flash")
    repeats = int(os.getenv("GEMINI_BENCH_REPEATS", "2"))
    max_secs = (os.getenv("GEMINI_LATENCY_MAX_SECS") or "").strip()
    max_ms = float(max_secs) * 1000.0 if max_secs else None
    include_assistant = os.getenv("GEMINI_BENCH_INCLUDE_ASSISTANT", "1").strip() != "0"

    client = genai.Client(api_key=api_key)
    schema = _response_schema()
    prompt_mode = os.getenv("GEMINI_BENCH_PROMPT_MODE", "both")
    prompt_variants = _prompt_variants(prompt_mode)
    scenarios = _selected_scenarios()
    print(
        f"[gemini-bench] model={model} repeats={repeats} "
        f"scenarios={','.join(str(s.scenario_id) for s in scenarios)} "
        f"include_assistant={include_assistant} prompt_mode={prompt_mode}"
    )

    for variant_name, variant_prompt in prompt_variants:
        variant_totals: List[float] = []
        variant_intent_hits = 0
        variant_intent_total = 0
        variant_scale_hits = 0
        variant_scale_total = 0

        print(f"[gemini-bench] ----- prompt_variant={variant_name} -----")

        for scenario in scenarios:
            transcript = _build_transcript(scenario.messages, include_assistant_turns=include_assistant)

            totals: List[float] = []
            llm_values: List[float] = []
            parse_values: List[float] = []
            chars_values: List[int] = []
            intent_ok_count = 0
            scale_ok_count = 0

            for _ in range(repeats):
                result = await _call_gemini(
                    client=client,
                    model=model,
                    system_prompt=variant_prompt,
                    transcript=transcript,
                    response_schema=schema,
                )
                payload = result["payload"]
                assert isinstance(payload, dict)
                assert "scores" in payload
                assert "confidence" in payload
                assert "appointment_intent" in payload

                flags = _quality_flags(
                    payload=payload,
                    expected_intent=scenario.expected_appointment_intent,
                )
                intent_ok_count += 1 if flags["intent_ok"] else 0
                scale_ok_count += 1 if flags["scale_looks_0_10"] else 0

                totals.append(result["total_ms"])
                llm_values.append(result["llm_ms"])
                parse_values.append(result["parse_ms"])
                chars_values.append(result["response_chars"])
                variant_totals.append(result["total_ms"])

            avg_total = statistics.fmean(totals)
            p95_total = _p95(totals)
            max_total = max(totals)
            avg_llm = statistics.fmean(llm_values)
            avg_parse = statistics.fmean(parse_values)
            avg_chars = statistics.fmean(chars_values)
            intent_acc = intent_ok_count / repeats
            scale_acc = scale_ok_count / repeats

            variant_intent_hits += intent_ok_count
            variant_intent_total += repeats
            variant_scale_hits += scale_ok_count
            variant_scale_total += repeats

            print(
                f"[gemini-bench] prompt={variant_name} scenario={scenario.scenario_id}:{scenario.name} "
                f"avg_total_ms={avg_total:.1f} p95_total_ms={p95_total:.1f} max_total_ms={max_total:.1f} "
                f"avg_llm_ms={avg_llm:.1f} avg_parse_ms={avg_parse:.1f} avg_response_chars={avg_chars:.1f} "
                f"intent_acc={intent_acc:.2f} scale_acc={scale_acc:.2f}"
            )

            if max_ms is not None:
                assert p95_total <= max_ms, (
                    f"Prompt {variant_name} escenario {scenario.scenario_id} "
                    f"p95={p95_total:.1f}ms supera umbral {max_ms:.1f}ms"
                )

        if variant_totals:
            print(
                f"[gemini-bench] prompt={variant_name} "
                f"global_avg_ms={statistics.fmean(variant_totals):.1f} "
                f"global_p95_ms={_p95(variant_totals):.1f} "
                f"global_max_ms={max(variant_totals):.1f} "
                f"intent_acc={(variant_intent_hits / max(1, variant_intent_total)):.2f} "
                f"scale_acc={(variant_scale_hits / max(1, variant_scale_total)):.2f}"
            )
