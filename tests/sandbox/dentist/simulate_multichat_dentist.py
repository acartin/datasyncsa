#!/usr/bin/env python3
"""
Simulador multi-conversacion para vertical Dentista sobre el stack activo.

Objetivo:
- Ejecutar conversaciones cortas en distintos escenarios odontologicos.
- Validar calidad de extraccion y scoring entre perfiles de paciente.

Uso:
  python3 tests/sandbox/dentist/simulate_multichat_dentist.py --conversation 1
  python3 tests/sandbox/dentist/simulate_multichat_dentist.py --all
  python3 tests/sandbox/dentist/simulate_multichat_dentist.py --list

Compatibilidad:
  python3 tests/sandbox/simulate_multichat_dentist.py --conversation 1
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

try:
    from simulate_chat_dentist import ChatSimulator, CLIENT_ID, INFERENCE_V2_URL
except ModuleNotFoundError:
    # Enables execution via wrapper where cwd/import path may differ.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from simulate_chat_dentist import ChatSimulator, CLIENT_ID, INFERENCE_V2_URL


SCENARIOS: Dict[int, Dict[str, object]] = {
    1: {
        "name": "dolor_agudo_urgente_con_datos_completos",
        "description": "Alta intencion, alta urgencia, servicio claro y solvencia declarada.",
        "messages": [
            "Hola, tengo dolor fuerte de muela desde anoche y necesito atencion hoy.",
            "Soy Mariana Rojas, correo mariana.rojas@gmail.com y telefono 8811-2299.",
            "Puedo pagar con tarjeta y seguro privado, no tengo problema con el costo.",
            "Quiero una cita de urgencia esta misma tarde, me duele demasiado.",
        ],
    },
    2: {
        "name": "limpieza_exploratoria_sin_urgencia",
        "description": "Interes bajo/medio, sin urgencia ni decision de agenda.",
        "messages": [
            "Hola, queria saber cuanto cuesta una limpieza dental.",
            "Solo estoy comparando opciones por ahora, aun no decido clinica.",
            "No tengo fecha definida, talvez el proximo mes.",
            "Cuando tenga tiempo les confirmo si agendo.",
        ],
    },
    3: {
        "name": "ortodoncia_planificada_timeline_medio",
        "description": "Paciente con necesidad clara, apertura alta y urgencia media.",
        "messages": [
            "Buenas, quiero valoracion para ortodoncia porque tengo apiñamiento.",
            "Me llamo Diego Solano, email diego.solano@correo.com, cel 8700-3322.",
            "Tengo presupuesto mensual de 120 dolares para el tratamiento.",
            "Podria iniciar en 1 o 2 meses, preferiblemente en horario nocturno.",
        ],
    },
    4: {
        "name": "implante_alta_solvencia_con_urgencia_media",
        "description": "Necesidad especializada, capacidad de pago alta y compromiso de seguimiento.",
        "messages": [
            "Necesito una evaluacion para implante dental en una pieza frontal.",
            "Soy Laura Jimenez, laura.jimenez@empresa.cr, telefono 8880-4411.",
            "Puedo pagar de contado si el plan me convence.",
            "Me gustaria cita esta semana para iniciar el proceso pronto.",
        ],
    },
    5: {
        "name": "consulta_incompleta_baja_conversion",
        "description": "Poca informacion util, baja apertura y baja intencion de avanzar.",
        "messages": [
            "Hola.",
            "Solo queria preguntar si atienden sabados.",
            "No puedo dar datos por ahora, luego les aviso.",
            "Gracias.",
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
    print(f"Chat API: {simulator.base_url}")
    print(f"Scoring API: {simulator.scoring_base_url}")
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

    latencies_ms: List[float] = []
    for i, query in enumerate(messages, 1):
        start = time.perf_counter()
        response = simulator.send_chat(query)
        latency_ms = (time.perf_counter() - start) * 1000.0

        if not response:
            continue

        latencies_ms.append(latency_ms)
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

    if latencies_ms:
        avg_ms = sum(latencies_ms) / len(latencies_ms)
        p95_index = max(0, min(len(latencies_ms) - 1, int(round(len(latencies_ms) * 0.95)) - 1))
        p95_ms = sorted(latencies_ms)[p95_index]
        print()
        print(f"Latencia promedio: {avg_ms:.2f} ms")
        print(f"Latencia p95: {p95_ms:.2f} ms")

    simulator.display_summary()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulador multi-conversacion para Dentista sobre chat activo + scoring-core."
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
        help=f"URL del chat activo (default: env CHAT_WEB_RENDERER_URL o {INFERENCE_V2_URL})",
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
