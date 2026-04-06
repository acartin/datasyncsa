#!/usr/bin/env python3
"""
Sandbox realtor para disparar el primer turno del grafo actual.

Objetivo principal:
- lanzar el grafo realtor
- confirmar que entra por `analyze_turn`
- recuperar la traza del turno desde ai-runtime

Usos:
  python tests/sandbox/realtor/simulate_chat_realtor.py
  python tests/sandbox/realtor/simulate_chat_realtor.py --query "Busco casa en Heredia"
  python tests/sandbox/realtor/simulate_chat_realtor.py --interactive
  python tests/sandbox/realtor/simulate_chat_realtor.py --full-trace
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests no esta instalado. Instala con: pip install requests")
    sys.exit(1)


DEFAULT_CLIENT_ID = os.getenv("CLIENT_ID", "64f357a0-98eb-44f1-9f41-6e615ed26180")
DEFAULT_USER_ID = os.getenv("REALTOR_SANDBOX_USER_ID", "sandbox-realtor-user")
DEFAULT_QUERY = "Hola, ando buscando casa en Heredia con 3 habitaciones y buen patio."
DEFAULT_RUNTIME_URL = os.getenv(
    "AI_RUNTIME_SANDBOX_API",
    f"http://127.0.0.1:{os.getenv('AI_RUNTIME_PORT', '8096')}/api/v1",
).rstrip("/")
DEFAULT_INTERNAL_TOKEN = os.getenv("INTERNAL_API_TOKEN")


class RealtorGraphProbe:
    def __init__(
        self,
        *,
        client_id: str,
        user_id: str,
        runtime_url: str,
        internal_token: str | None = None,
        timeout_seconds: int = 30,
    ):
        self.client_id = client_id
        self.user_id = user_id
        self.runtime_url = runtime_url
        self.internal_token = (internal_token or "").strip() or None
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session_id: str | None = None
        self.conversation_id: str | None = None

    def _trace_headers(self) -> dict[str, str]:
        if not self.internal_token:
            return {}
        return {"X-Internal-Token": self.internal_token}

    def check_health(self, target: str) -> bool:
        base_url = self.runtime_url
        try:
            response = self.session.get(f"{base_url}/health", timeout=10)
            if response.status_code != 200:
                print(f"ERROR health {target}: HTTP {response.status_code}")
                print(response.text)
                return False
            payload = response.json()
            print(f"Servicio: {payload.get('service', 'unknown')}")
            print(f"Status: {payload.get('status', 'unknown')}")
            print(f"Endpoint activo: {base_url}")
            return True
        except Exception as exc:
            print(f"ERROR conectando con {base_url}/health: {exc}")
            return False

    def send_turn(self, query: str, target: str) -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "clientId": self.client_id,
            "userId": self.user_id,
            "flow": "realtor_flow",
            "message": query,
            "metadata": {
                "sandbox": "realtor",
                "purpose": "first-node-probe",
            },
        }
        if self.session_id:
            payload["sessionId"] = self.session_id
        if self.conversation_id:
            payload["conversationId"] = self.conversation_id
        endpoint = f"{self.runtime_url}/chat"

        try:
            response = self.session.post(endpoint, json=payload, timeout=self.timeout_seconds)
        except Exception as exc:
            print(f"ERROR enviando request: {exc}")
            return None

        if response.status_code != 200:
            print(f"ERROR {response.status_code} en {endpoint}")
            print(response.text)
            return None

        data = response.json()
        self.session_id = data.get("session_id", self.session_id)
        self.conversation_id = (
            data.get("conversation_id")
            or data.get("conversationId")
            or self.conversation_id
        )
        return data

    def fetch_turn_trace(self, turn: int) -> dict[str, Any] | None:
        if not self.session_id:
            print("No hay session_id. Para recuperar trazas usa --target runtime.")
            return None
        endpoint = (
            f"{self.runtime_url}/debug/turn-traces/clients/{self.client_id}"
            f"/sessions/{self.session_id}/turns/{turn}"
        )
        try:
            response = self.session.get(endpoint, headers=self._trace_headers(), timeout=15)
        except Exception as exc:
            print(f"ERROR leyendo turn trace: {exc}")
            return None

        if response.status_code == 401:
            print("ERROR: el endpoint de trazas requiere INTERNAL_API_TOKEN.")
            print("Tip: exporta INTERNAL_API_TOKEN o pasa --internal-token.")
            return None
        if response.status_code != 200:
            print(f"ERROR {response.status_code} leyendo turn trace")
            print(response.text)
            return None
        return response.json()

    @staticmethod
    def _extract_first_node_events(trace_payload: dict[str, Any]) -> list[dict[str, Any]]:
        events = trace_payload.get("events", [])
        interesting = {
            "analyze_turn",
            "after_analyze_turn",
        }
        return [event for event in events if event.get("name") in interesting]

    @staticmethod
    def _print_trace_summary(trace_payload: dict[str, Any], full_trace: bool) -> None:
        print()
        print("=" * 72)
        print("TURN TRACE")
        print("=" * 72)
        print(f"trace_id: {trace_payload.get('trace_id')}")
        print(f"turn: {trace_payload.get('turn')}")
        print(f"status: {trace_payload.get('status')}")
        print(f"session_id: {trace_payload.get('session_id')}")
        print(f"conversation_id: {trace_payload.get('conversation_id')}")

        events = trace_payload.get("events", [])
        filtered = events if full_trace else RealtorGraphProbe._extract_first_node_events(trace_payload)
        label = "EVENTOS COMPLETOS" if full_trace else "PRIMER NODO"
        print()
        print(label)
        print("-" * 72)
        if not filtered:
            print("No se encontraron eventos para mostrar.")
            return

        for event in filtered:
            payload = event.get("payload") or {}
            print(f"[{event.get('seq', '?'):>2}] {event.get('kind', '-'):<12} {event.get('name', '-')}")
            if event.get("kind") == "router":
                print(f"     decision: {payload.get('decision')}")
            elif event.get("kind") == "llm_end":
                result = payload.get("result")
                print("     result:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif event.get("kind") == "node_end":
                state_updates = payload.get("state_updates", {})
                print(f"     update_keys: {', '.join(payload.get('update_keys', [])) or '-'}")
                print("     state_updates:")
                print(json.dumps(state_updates, indent=2, ensure_ascii=False))
            elif event.get("kind") in {"node_start", "llm_start"}:
                print("     payload:")
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print("     payload:")
                print(json.dumps(payload, indent=2, ensure_ascii=False))

    @staticmethod
    def print_chat_response(response: dict[str, Any], target: str) -> None:
        print()
        print("=" * 72)
        print(f"RESPUESTA ({target})")
        print("=" * 72)
        print(json.dumps(response, indent=2, ensure_ascii=False))

    def run_single(self, query: str, target: str, show_trace: bool, full_trace: bool) -> int:
        if not self.check_health(target):
            return 1

        response = self.send_turn(query, target)
        if not response:
            return 1

        self.print_chat_response(response, target)
        if not show_trace:
            return 0
        turn = ((response.get("metadata") or {}).get("turn")) or 1
        trace_payload = self.fetch_turn_trace(int(turn))
        if trace_payload:
            self._print_trace_summary(trace_payload, full_trace=full_trace)
        return 0

    def run_interactive(self, target: str, show_trace: bool, full_trace: bool) -> int:
        if not self.check_health(target):
            return 1

        print()
        print("=" * 72)
        print("MODO INTERACTIVO REALTOR ANALYZE-TURN PROBE")
        print("=" * 72)
        print(f"client_id: {self.client_id}")
        print(f"user_id: {self.user_id}")
        print(f"target: {target}")
        print("Escribe 'exit' para salir.")

        while True:
            try:
                query = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo...")
                return 0
            if not query:
                continue
            if query.lower() == "exit":
                return 0
            exit_code = self.run_single(query, target, show_trace=show_trace, full_trace=full_trace)
            if exit_code != 0:
                return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Sandbox realtor para disparar el primer nodo real del grafo actual.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Mensaje a enviar en el primer turno.")
    parser.add_argument("--interactive", action="store_true", help="Modo interactivo.")
    parser.add_argument(
        "--target",
        choices=("runtime",),
        default="runtime",
        help="runtime = ai-runtime directo con trazas.",
    )
    parser.add_argument("--client-id", default=DEFAULT_CLIENT_ID, help=f"Tenant realtor (default: {DEFAULT_CLIENT_ID})")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help=f"User ID del sandbox (default: {DEFAULT_USER_ID})")
    parser.add_argument("--runtime-url", default=DEFAULT_RUNTIME_URL, help=f"Base URL de ai-runtime (default: {DEFAULT_RUNTIME_URL})")
    parser.add_argument(
        "--internal-token",
        default=DEFAULT_INTERNAL_TOKEN,
        help="Token para endpoints debug de ai-runtime. Si no se pasa, usa INTERNAL_API_TOKEN.",
    )
    parser.add_argument("--no-trace", action="store_true", help="No pedir turn trace despues del request.")
    parser.add_argument("--full-trace", action="store_true", help="Mostrar todos los eventos del turno, no solo el primer nodo.")
    args = parser.parse_args()

    probe = RealtorGraphProbe(
        client_id=args.client_id,
        user_id=args.user_id,
        runtime_url=args.runtime_url,
        internal_token=args.internal_token,
    )

    if args.interactive:
        return probe.run_interactive(
            target=args.target,
            show_trace=not args.no_trace,
            full_trace=args.full_trace,
        )
    return probe.run_single(
        args.query,
        args.target,
        show_trace=not args.no_trace,
        full_trace=args.full_trace,
    )


if __name__ == "__main__":
    raise SystemExit(main())
