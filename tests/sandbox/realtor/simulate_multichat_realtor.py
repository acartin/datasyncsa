#!/usr/bin/env python3
"""
Simulador multi-conversacion para vertical Realtor (ai-runtime).

Objetivo:
- Ejecutar 5 conversaciones realistas de inmobiliaria costarricense.
- Validar persistencia en lead_conversations y scoring asyncrono.
- Confirmar scoring_status="queued" por turno y scorecard final por lead.

Uso:
  python3 tests/sandbox/realtor/simulate_multichat_realtor.py --conversation 1
  python3 tests/sandbox/realtor/simulate_multichat_realtor.py --all
  python3 tests/sandbox/realtor/simulate_multichat_realtor.py --list
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    print("ERROR: requests no esta instalado. Instala con: pip install requests")
    sys.exit(1)


def _load_dotenv(repo_root: Path) -> None:
    """Load .env from repo root into os.environ (simple key=value parser, no substitution)."""
    env_file = repo_root / ".env"
    if not env_file.exists():
        return
    with env_file.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw_value = line.partition("=")
            key = key.strip()
            # Skip lines with shell substitution (${...}) — those need shell expansion
            if "${" in raw_value:
                continue
            if key and key not in os.environ:
                os.environ[key] = raw_value.strip()


# Load .env from repo root (two levels up from this file)
_load_dotenv(Path(__file__).resolve().parent.parent.parent.parent)


CLIENT_ID = "64f357a0-98eb-44f1-9f41-6e615ed26180"
AI_RUNTIME_PORT = os.getenv("AI_RUNTIME_PORT", "8096")
SCORING_CORE_PORT = os.getenv("SCORING_CORE_PORT", "8097")
RUNTIME_URL = os.getenv(
    "AI_RUNTIME_SANDBOX_API",
    f"http://127.0.0.1:{AI_RUNTIME_PORT}/api/v1",
).rstrip("/")
SCORING_URL = os.getenv(
    "SCORING_CORE_SANDBOX_API",
    f"http://127.0.0.1:{SCORING_CORE_PORT}/api/v1",
).rstrip("/")
INTERNAL_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")

# Docker container & DB settings (used to resolve lead_id from conversation_id)
ENV_PREFIX = os.getenv("ENV_PREFIX", "ds-dev")
DB_CONTAINER = os.getenv("DB_CONTAINER", f"{ENV_PREFIX}-infra-postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_NAME = os.getenv("DB_NAME", "agentic")


SCENARIOS: Dict[int, Dict[str, Any]] = {
    1: {
        "name": "alta_intencion_casa_heredia",
        "description": "Comprador claro, 3 habitaciones Heredia, da nombre/email/telefono, quiere visita.",
        "messages": [
            "Hola, busco una casa en Heredia con 3 habitaciones y buen patio para mis hijos.",
            "Mi nombre es Carlos Ulate, correo carlos.ulate@gmail.com y mi telefono es 8833-1122.",
            "El presupuesto maximo que tengo es 180 mil dolares, podria estirar un poco si vale la pena.",
            "Me gustaria ir a ver alguna opcion este fin de semana, tengo disponibilidad sabado o domingo.",
        ],
    },
    2: {
        "name": "inversionista_presupuesto_alto",
        "description": "Inversionista, busca apartamento 200-250k para alquilar, datos completos.",
        "messages": [
            "Buenos dias, estoy buscando un apartamento para inversion, zona GAM preferiblemente.",
            "El rango que manejo es entre 200 y 250 mil dolares, me interesa la plusvalia y rentabilidad.",
            "Soy Andrea Mora, contacto andrea.mora@inversiones.cr y celular 8744-5566.",
            "Quiero ver opciones pronto, puedo agendar una llamada esta semana para que me presenten algo.",
        ],
    },
    3: {
        "name": "primer_comprador_presupuesto_limitado",
        "description": "Primera vivienda, presupuesto 90k, da datos progresivamente.",
        "messages": [
            "Hola buenas, queria saber si tienen casas economicas, es para primera vivienda.",
            "Tengo como maximo 90 mil dolares, estoy recien casado y buscamos algo sencillo.",
            "Nos interesan Cartago o Alajuela, lo que sea mas accesible para ese presupuesto.",
            "Me llamo Luis Badilla, mi email es luisbadilla87@hotmail.com, al 8900-2211.",
        ],
    },
    4: {
        "name": "busqueda_vaga_sin_urgencia",
        "description": "Consulta vaga, sin urgencia, sin datos de contacto, scoring bajo esperado.",
        "messages": [
            "Hola, ando viendo opciones de casas pero sin apuro.",
            "No tengo claro todavia la zona ni el presupuesto.",
            "Solo estaba mirando que hay disponible por si acaso.",
            "Gracias, ya les aviso si me decido.",
        ],
    },
    5: {
        "name": "lead_negativo_sin_datos",
        "description": "Engagement minimo, rehusa dar datos, sin intencion real, scoring muy bajo.",
        "messages": [
            "Hola.",
            "Solo queria saber si venden casas en San Jose.",
            "No quiero dar datos todavia.",
            "No gracias, solo estaba curioseando.",
        ],
    },
}


def _resolve_lead_id_via_docker(conversation_id: str) -> str | None:
    """Query lead_id from lead_conversations using docker exec psql."""
    sql = f"SELECT lead_id FROM lead_conversations WHERE conversation_id = '{conversation_id}' LIMIT 1;"
    try:
        result = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME, "-t", "-A", "-c", sql],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout.strip()
        if output and len(output) == 36:  # UUID length
            return output
        return None
    except Exception as exc:
        print(f"  [warn] No se pudo resolver lead_id via docker: {exc}")
        return None


class RealtorChatSimulator:
    def __init__(
        self,
        *,
        client_id: str,
        runtime_url: str,
        scoring_url: str,
        internal_token: str,
        user_id: str = "sandbox-realtor-multichat",
        timeout: int = 45,
    ):
        self.client_id = client_id
        self.runtime_url = runtime_url
        self.scoring_url = scoring_url
        self.internal_token = internal_token
        self.user_id = user_id
        self.timeout = timeout
        self.session = requests.Session()
        self.session_id: str | None = None
        self.conversation_id: str | None = None
        self.history: List[dict] = []

    def reset(self) -> None:
        self.session_id = None
        self.conversation_id = None
        self.history = []

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self.internal_token:
            h["X-Internal-Token"] = self.internal_token
        return h

    def check_health(self) -> bool:
        try:
            resp = self.session.get(f"{self.runtime_url}/health", timeout=10)
            if resp.status_code != 200:
                print(f"  ERROR health ai-runtime: HTTP {resp.status_code}")
                return False
            data = resp.json()
            print(f"  ai-runtime: {data.get('service','?')} [{data.get('status','?')}]")
            return True
        except Exception as exc:
            print(f"  ERROR ai-runtime health: {exc}")
            return False

    def check_scoring_health(self) -> bool:
        try:
            resp = self.session.get(f"{self.scoring_url}/health", timeout=10)
            if resp.status_code != 200:
                print(f"  ERROR health scoring-core: HTTP {resp.status_code}")
                return False
            data = resp.json()
            print(f"  scoring-core: {data.get('service','?')} [{data.get('status','?')}]")
            return True
        except Exception as exc:
            print(f"  WARN scoring-core health: {exc} (scoring poll puede fallar)")
            return False

    def send_turn(self, message: str) -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "client_id": self.client_id,
            "user_id": self.user_id,
            "flow": "realtor_flow",
            "message": message,
            "metadata": {"channel": "webchat", "sandbox": "realtor_multichat"},
        }
        if self.session_id:
            payload["session_id"] = self.session_id
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        try:
            resp = self.session.post(
                f"{self.runtime_url}/chat",
                json=payload,
                timeout=self.timeout,
            )
        except Exception as exc:
            print(f"  ERROR enviando turno: {exc}")
            return None

        if resp.status_code != 200:
            print(f"  ERROR HTTP {resp.status_code}: {resp.text[:300]}")
            return None

        data = resp.json()
        self.session_id = data.get("session_id", self.session_id)
        self.conversation_id = (
            data.get("conversation_id")
            or data.get("conversationId")
            or self.conversation_id
        )
        return data

    def get_active_scoring_model(self) -> dict[str, Any] | None:
        try:
            resp = self.session.get(
                f"{self.scoring_url}/scoring/models/active",
                params={"client_id": self.client_id},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def wait_for_scorecard(
        self,
        lead_id: str,
        *,
        max_wait: int = 40,
        poll_interval: int = 4,
    ) -> dict[str, Any] | None:
        """Poll scoring-core until scorecard is ready or timeout."""
        deadline = time.monotonic() + max_wait
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            try:
                resp = self.session.get(
                    f"{self.scoring_url}/leads/{lead_id}/scorecards/latest",
                    params={"client_id": self.client_id},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 404:
                    pass  # not ready yet
                else:
                    print(f"  [warn] scoring poll HTTP {resp.status_code}")
            except Exception as exc:
                print(f"  [warn] scoring poll error: {exc}")

            remaining = deadline - time.monotonic()
            if remaining > 0:
                wait = min(poll_interval, remaining)
                print(f"  [scoring] esperando resultado (intento {attempt}, {int(remaining)}s restantes)...", end="\r")
                time.sleep(wait)

        print()
        return None

    def display_turn(
        self,
        response: dict[str, Any],
        turn_num: int,
        query: str,
    ) -> None:
        scoring_status = response.get("scoring_status", "—")
        answer = response.get("answer", "")
        metadata = response.get("metadata") or {}
        render_mode = response.get("render_mode") or "—"
        print()
        print(f"  --- Turno {turn_num} ---")
        print(f"  Usuario : {query}")
        print(f"  Bot     : {answer}")
        print(f"  scoring_status : {scoring_status}")
        print(f"  render_mode    : {render_mode}")
        print(f"  turn           : {metadata.get('turn', '?')}")
        if response.get("escalated"):
            print("  [ESCALADO]")

    def display_scorecard(self, scorecard: dict[str, Any]) -> None:
        print()
        print("  ┌── SCORECARD ───────────────────────────────────────────────┐")
        print(f"  │ scorecard_id : {scorecard.get('id', '—')}")
        print(f"  │ lead_id      : {scorecard.get('lead_id', '—')}")
        print(f"  │ score_total  : {scorecard.get('score_total', '—')}")
        print(f"  │ tier         : {scorecard.get('tier', '—')}")
        print(f"  │ status       : {scorecard.get('status', '—')}")
        items = scorecard.get("items") or []
        if items:
            print(f"  │ items ({len(items)}):")
            for item in items:
                key = item.get("criterion_key") or item.get("criterionKey") or "?"
                val = item.get("value")
                score = item.get("score")
                print(f"  │   {key:<30} val={val}  score={score}")
        print("  └────────────────────────────────────────────────────────────┘")

    def display_summary(self) -> None:
        latencies = [h["latency_ms"] for h in self.history if h.get("latency_ms")]
        if not latencies:
            return
        avg = sum(latencies) / len(latencies)
        p95_idx = max(0, min(len(latencies) - 1, int(round(len(latencies) * 0.95)) - 1))
        p95 = sorted(latencies)[p95_idx]
        print()
        print(f"  Latencia promedio : {avg:.0f} ms")
        print(f"  Latencia p95      : {p95:.0f} ms")
        print(f"  Turnos completados: {len(latencies)}")
        print(f"  conversation_id   : {self.conversation_id or '—'}")


def _print_scenarios() -> None:
    print("\nEscenarios disponibles:\n")
    for key in sorted(SCENARIOS.keys()):
        item = SCENARIOS[key]
        print(f"  {key}. {item['name']}")
        print(f"     {item['description']}")
    print()


def _run_scenario(
    scenario_id: int,
    *,
    client_id: str,
    runtime_url: str,
    scoring_url: str,
    internal_token: str,
    skip_scoring: bool = False,
) -> None:
    scenario = SCENARIOS[scenario_id]
    messages: List[str] = list(scenario["messages"])

    simulator = RealtorChatSimulator(
        client_id=client_id,
        runtime_url=runtime_url,
        scoring_url=scoring_url,
        internal_token=internal_token,
        user_id=f"sandbox-realtor-s{scenario_id}",
    )
    simulator.reset()

    print()
    print("=" * 67)
    print(f"ESCENARIO {scenario_id}: {scenario['name']}")
    print("=" * 67)
    print(f"Descripcion : {scenario['description']}")
    print(f"Mensajes    : {len(messages)}")
    print(f"Cliente     : {client_id}")
    print(f"Runtime     : {runtime_url}")

    if not simulator.check_health():
        print("ERROR: ai-runtime no disponible, saltando escenario.")
        return

    if not skip_scoring:
        simulator.check_scoring_health()

    # Show active scoring model
    model = simulator.get_active_scoring_model()
    if model:
        print()
        print(f"  Scoring model v{model.get('model_version', '?')}")
        criteria = model.get("criteria") or []
        if criteria:
            keys = [c.get("criterion_key") or c.get("criterionKey") for c in criteria]
            print(f"  Criterios : {', '.join(filter(None, keys))}")

    print()

    # Execute turns
    for i, message in enumerate(messages, 1):
        t0 = time.perf_counter()
        response = simulator.send_turn(message)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        if not response:
            print(f"  ERROR en turno {i}, continuando...")
            continue

        simulator.history.append(
            {
                "turn": i,
                "query": message,
                "conversation_id": simulator.conversation_id,
                "scoring_status": response.get("scoring_status"),
                "latency_ms": latency_ms,
            }
        )
        simulator.display_turn(response, i, message)

    simulator.display_summary()

    # Resolve lead_id and fetch scorecard
    if skip_scoring:
        return

    conversation_id = simulator.conversation_id
    if not conversation_id:
        print("\n  [scoring] No hay conversation_id, omitiendo scorecard.")
        return

    print(f"\n  [scoring] Resolviendo lead_id para conversation_id={conversation_id}...")
    lead_id = _resolve_lead_id_via_docker(conversation_id)
    if not lead_id:
        print("  [scoring] No se pudo resolver lead_id. Scorecard no disponible.")
        return

    print(f"  [scoring] lead_id={lead_id}, esperando scorecard...")
    scorecard = simulator.wait_for_scorecard(lead_id, max_wait=45, poll_interval=4)
    if scorecard:
        print()
        simulator.display_scorecard(scorecard)
    else:
        print("\n  [scoring] Scorecard no disponible dentro del tiempo de espera.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulador multi-conversacion para Realtor (ai-runtime)."
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
        help="Ejecutar los 5 escenarios.",
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
        "--runtime-url",
        type=str,
        default=RUNTIME_URL,
        help=f"URL base de ai-runtime (default: {RUNTIME_URL})",
    )
    parser.add_argument(
        "--scoring-url",
        type=str,
        default=SCORING_URL,
        help=f"URL base de scoring-core (default: {SCORING_URL})",
    )
    parser.add_argument(
        "--internal-token",
        type=str,
        default=INTERNAL_TOKEN,
        help="Token interno (default: INTERNAL_API_TOKEN env)",
    )
    parser.add_argument(
        "--skip-scoring",
        action="store_true",
        help="Omitir espera de scorecard al final de cada escenario.",
    )
    args = parser.parse_args()

    if args.list:
        _print_scenarios()
        return

    kwargs = dict(
        client_id=args.client_id,
        runtime_url=args.runtime_url,
        scoring_url=args.scoring_url,
        internal_token=args.internal_token,
        skip_scoring=args.skip_scoring,
    )

    if args.all:
        for sid in sorted(SCENARIOS.keys()):
            _run_scenario(sid, **kwargs)
        return

    if args.conversation not in SCENARIOS:
        valid = ", ".join(str(k) for k in sorted(SCENARIOS.keys()))
        raise SystemExit(f"ERROR: escenario invalido '{args.conversation}'. Usa: {valid}")

    _run_scenario(args.conversation, **kwargs)


if __name__ == "__main__":
    main()
