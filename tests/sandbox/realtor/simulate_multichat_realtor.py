#!/usr/bin/env python3
"""
Simulador multi-conversacion para vertical Realtor (v2).

Objetivo:
- Ejecutar conversaciones cortas en distintos escenarios.
- Validar calidad de extraccion y scoring entre perfiles de lead.

Uso:
  python3 tests/sandbox/realtor/simulate_multichat_realtor.py --conversation 1
  python3 tests/sandbox/realtor/simulate_multichat_realtor.py --all
  python3 tests/sandbox/realtor/simulate_multichat_realtor.py --list

Compatibilidad:
  python3 tests/sandbox/simulate_multichat_realtor.py --conversation 1
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List

try:
    from simulate_chat_realtor import ChatSimulator, CLIENT_ID, INFERENCE_V2_URL
except ModuleNotFoundError:
    # Enables execution via wrapper where cwd/import path may differ.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from simulate_chat_realtor import ChatSimulator, CLIENT_ID, INFERENCE_V2_URL


SCENARIOS: Dict[int, Dict[str, object]] = {
    1: {
        "name": "comprador_caliente_preaprobado",
        "description": "Alta intencion, timeline corto, presupuesto claro y preaprobacion.",
        "messages": [
            "Hola, vi una casa en Heredia y me interesa comprar pronto.",
            "Me llamo Ana Vargas, mi correo es ana.vargas@gmail.com y mi telefono 8899-1122.",
            "Tenemos preaprobacion bancaria con BAC y presupuesto entre 125 mil y 145 mil dolares.",
            "Queremos agendar visita esta misma semana, idealmente jueves en la tarde.",
        ],
    },
    2: {
        "name": "exploratorio_sin_urgencia",
        "description": "Interes bajo/medio, sin urgencia ni datos financieros concretos.",
        "messages": [
            "Hola, solo estoy viendo opciones por ahora.",
            "Tal vez me mude el proximo ano, aun no tengo fecha definida.",
            "No tengo preaprobacion ni presupuesto cerrado todavia.",
            "Solo queria saber en que zonas de Alajuela hay casas familiares.",
        ],
    },
    3: {
        "name": "familia_timeline_medio",
        "description": "Familia con requerimientos claros y contacto completo, sin financiamiento aprobado.",
        "messages": [
            "Busco apartamento en Escazu con 2 o 3 habitaciones y parqueo.",
            "Soy Carlos Mena, correo carlos.mena@correo.com, telefono 8777-3344.",
            "Nuestro presupuesto ronda los 95 mil dolares pero aun no tenemos preaprobacion.",
            "Nos gustaria mudarnos en unos 4 a 6 meses.",
        ],
    },
    4: {
        "name": "inversionista_contado_urgente",
        "description": "Lead inversionista, alta capacidad financiera y alta urgencia.",
        "messages": [
            "Buenas, busco propiedad para inversion en Heredia centro.",
            "Tengo fondos al contado por 200 mil dolares.",
            "Mi nombre es Laura Campos y mi correo es laura.campos@capital.cr.",
            "Si encaja, quiero visitar manana en la manana.",
        ],
    },
    5: {
        "name": "curioso_baja_conversion",
        "description": "Conversacion corta con poca informacion util y baja intencion de avance.",
        "messages": [
            "Hola, vi un anuncio y queria saber el precio nada mas.",
            "Estoy comparando por curiosidad, aun no pienso moverme.",
            "No tengo presupuesto definido ni fecha, luego les escribo.",
            "Gracias, por ahora no necesito agendar visita.",
        ],
    },
}


def _print_scenarios() -> None:
    print("\nEscenarios disponibles:\n")
    for key in sorted(SCENARIOS.keys()):
        item = SCENARIOS[key]
        print(f"  {key}. {item['name']}: {item['description']}")
    print()


def _run_scenario(
    scenario_id: int,
    *,
    client_id: str,
    url: str,
    model_id: str | None,
    discover_endpoints: bool,
) -> None:
    scenario = SCENARIOS[scenario_id]
    messages: List[str] = list(scenario["messages"])  # type: ignore[arg-type]

    simulator = ChatSimulator(
        client_id=client_id,
        base_url=url,
        model_id=model_id,
        discover_endpoints=discover_endpoints,
    )

    print()
    print("=" * 67)
    print(f"ESCENARIO {scenario_id}: {scenario['name']}")
    print("=" * 67)
    print(f"Descripcion: {scenario['description']}")
    print(f"Mensajes: {len(messages)}")
    print(f"Cliente: {client_id}")
    print(f"API: {simulator.base_url}")
    print()

    if not simulator.check_health():
        print("ERROR: Servicio no disponible")
        return
    if not simulator.validate_expected_model():
        print("ERROR: Modelo esperado no activo para este cliente")
        return

    model = simulator.get_active_model()
    if model:
        print()
        print(f"Modelo activo: v{model.get('model_version', model.get('modelVersion'))}")
        criteria = model.get("criteria", [])
        if criteria:
            criterion_keys = [c.get("criterion_key", c.get("criterionKey")) for c in criteria]
            print(f"Criterios: {', '.join(filter(None, criterion_keys))}")

    for i, query in enumerate(messages, 1):
        response, latency_ms = simulator.timed_send_chat(query)
        if not response:
            continue
        simulator.message_latencies_ms.append(latency_ms)
        simulator.history.append(
            {
                "query": query,
                "leadId": response.get("leadId"),
                "conversationId": response.get("conversationId"),
                "scorecardId": response.get("scorecardId"),
                "scorecard": response.get("scorecard"),
                "latency_ms": latency_ms,
            }
        )
        simulator.display_response(response, i, query)

    simulator.display_summary()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulador multi-conversacion para Realtor v2."
    )
    parser.add_argument(
        "--conversation",
        type=int,
        default=1,
        help="Numero de conversacion a ejecutar (1-5).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ejecutar los 5 escenarios (genera 5 leads).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Listar escenarios disponibles y salir.",
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=CLIENT_ID,
        help=f"Client ID (default: {CLIENT_ID})",
    )
    parser.add_argument(
        "--model-id",
        type=str,
        default=os.getenv("MODEL_ID"),
        help="Model ID esperado (opcional; por defecto usa el modelo del cliente).",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("INFERENCE_V2_API", INFERENCE_V2_URL),
        help=f"URL del API v2 (default: env INFERENCE_V2_API o {INFERENCE_V2_URL})",
    )
    parser.add_argument(
        "--discover-endpoints",
        action="store_true",
        help="Intentar endpoints alternativos (solo diagnostico).",
    )
    args = parser.parse_args()

    if args.list:
        _print_scenarios()
        return

    if args.all:
        for scenario_id in sorted(SCENARIOS.keys()):
            _run_scenario(
                scenario_id,
                client_id=args.client_id,
                url=args.url,
                model_id=args.model_id,
                discover_endpoints=args.discover_endpoints,
            )
        return

    if args.conversation not in SCENARIOS:
        valid = ", ".join(str(key) for key in sorted(SCENARIOS.keys()))
        raise SystemExit(f"ERROR: conversacion invalida '{args.conversation}'. Usa: {valid}")

    _run_scenario(
        args.conversation,
        client_id=args.client_id,
        url=args.url,
        model_id=args.model_id,
        discover_endpoints=args.discover_endpoints,
    )


if __name__ == "__main__":
    main()
