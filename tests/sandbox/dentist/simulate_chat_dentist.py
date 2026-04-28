#!/usr/bin/env python3
"""
Simulador de flujo Chat activo -> Lead -> Scorecard.

Uso:
  python tests/sandbox/dentist/simulate_chat_dentist.py              # modo automatico
  python tests/sandbox/dentist/simulate_chat_dentist.py --auto       # modo automatico
  python tests/sandbox/dentist/simulate_chat_dentist.py --query "Hola"  # mensaje unico
  python tests/sandbox/dentist/simulate_chat_dentist.py --interactive   # modo interactivo

Compatibilidad:
  python tests/sandbox/simulate_chat_dentist.py  # wrapper legacy

Comandos interactivos:
  exit      - Terminar sesion
  history   - Ver historial de mensajes
  scorecard - Ver ultimo scorecard detallado
  db        - Mostrar queries SQL para verificar en DB
  reset     - Iniciar nueva conversacion
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests no esta instalado. Instala con: pip install requests")
    sys.exit(1)


CLIENT_ID = "66fc0a3b-c8d3-4707-8471-c751c642852d"
CHAT_WEB_RENDERER_URL = os.getenv("CHAT_WEB_RENDERER_URL", "http://localhost:8086").rstrip("/")
SCORING_CORE_URL = os.getenv("SCORING_CORE_API", "http://localhost:8097").rstrip("/")
SCORING_API_PREFIX = os.getenv("SCORING_API_PREFIX", "/api/v1")
INFERENCE_V2_URL = CHAT_WEB_RENDERER_URL

AUTO_MESSAGES = [
    "Hola, necesito una cita dental",
    "Me llamo Eliana del Toro, mi email es Eliana@zonaplus.com",
    "Tengo dolor de muela desde hace 3 dias",
    "Puedo pagar con tarjeta de credito",
    "Mi telefono es 8888-1234, prefieren contactarme por WhatsApp",
    "Quisiera una cita lo mas pronto posible, hoy si se puede",
]


class ChatSimulator:
    def __init__(self, client_id: str, base_url: str, model_id: str | None = None, discover_endpoints: bool = False):
        self.client_id = client_id
        self.model_id = model_id
        self.base_url = self._normalize_base_url(base_url)
        self.scoring_base_url = self._normalize_scoring_base_url(SCORING_CORE_URL)
        self.channel = os.getenv("CHANNEL", "web_html")
        self.channel_user_id = os.getenv("CHANNEL_USER_ID", f"dentist-sandbox-{int(time.time())}")
        self.lead_id: str | None = None
        self.conversation_id: str | None = None
        self.session_id: str | None = None
        self.last_scoring_job_id: str | None = None
        self.history: list[dict[str, Any]] = []
        self.scorecards: list[dict[str, Any]] = []
        self.session = requests.Session()
        if discover_endpoints:
            self.candidate_urls = self._build_candidate_urls(self.base_url)
        else:
            self.candidate_urls = [self.base_url]
        self.scoring_candidates = self._build_scoring_candidates(self.scoring_base_url)

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        normalized = (url or "").strip().rstrip("/")
        if not normalized:
            return CHAT_WEB_RENDERER_URL
        for suffix in ("/chat", "/api/v2", "/api"):
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
        return normalized or CHAT_WEB_RENDERER_URL

    @staticmethod
    def _normalize_scoring_base_url(url: str) -> str:
        normalized = (url or "").strip().rstrip("/")
        if not normalized:
            normalized = SCORING_CORE_URL
        prefix = SCORING_API_PREFIX.strip()
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        normalized_prefix = prefix.rstrip("/")
        if normalized.endswith(normalized_prefix):
            return normalized
        return f"{normalized}{normalized_prefix}"

    def _build_candidate_urls(self, explicit_url: str) -> list[str]:
        env_candidates = [
            os.getenv("CHAT_WEB_RENDERER_URL"),
            os.getenv("INFERENCE_V2_API"),
            os.getenv("INFERENCE_V2_URL"),
        ]
        defaults = [
            explicit_url,
            CHAT_WEB_RENDERER_URL,
            "http://localhost:8086",
            "http://127.0.0.1:8086",
            "http://chat-web-renderer-api:8000",
        ]
        seen: set[str] = set()
        candidates: list[str] = []
        for raw in env_candidates + defaults:
            if not raw:
                continue
            normalized = self._normalize_base_url(raw)
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(normalized)
        return candidates

    def _build_scoring_candidates(self, explicit_url: str) -> list[str]:
        env_candidates = [
            os.getenv("SCORING_CORE_API"),
            os.getenv("SCORING_BASE_URL"),
        ]
        defaults = [
            explicit_url,
            SCORING_CORE_URL,
            "http://localhost:8097",
            "http://127.0.0.1:8097",
        ]
        seen: set[str] = set()
        candidates: list[str] = []
        for raw in env_candidates + defaults:
            if not raw:
                continue
            normalized = self._normalize_scoring_base_url(raw)
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(normalized)
        return candidates

    @staticmethod
    def _extract_chat_text(response_json: dict[str, Any]) -> str:
        for comp in response_json.get("components") or []:
            if str(comp.get("type") or "").strip().lower() == "chat":
                return str(comp.get("text") or "").strip()
        return ""

    def check_health(self) -> bool:
        last_error = None

        for candidate in self.candidate_urls:
            try:
                resp = self.session.get(f"{candidate}/health", timeout=10)
                if resp.status_code != 200:
                    last_error = f"chat HTTP {resp.status_code}"
                    continue
                self.base_url = candidate
                data = resp.json()
                print(f"Servicio chat: {data.get('service', 'unknown')}")
                print(f"Version chat: {data.get('version', 'unknown')}")
                print(f"Endpoint chat activo: {self.base_url}")
                break
            except Exception as exc:
                last_error = str(exc)
        else:
            print("ERROR: no se pudo conectar al chat activo.")
            for candidate in self.candidate_urls:
                print(f"  - {candidate}/health")
            if last_error:
                print(f"Ultimo error: {last_error}")
            print("Tip: exporta CHAT_WEB_RENDERER_URL con la URL correcta, por ejemplo:")
            print("  CHAT_WEB_RENDERER_URL=http://localhost:8086")
            return False

        for candidate in self.scoring_candidates:
            try:
                resp = self.session.get(f"{candidate}/health", timeout=10)
                if resp.status_code != 200:
                    last_error = f"scoring HTTP {resp.status_code}"
                    continue
                data = resp.json()
                if str(data.get("service") or "").strip().lower() != "scoring-core":
                    last_error = f"servicio inesperado: {data.get('service')}"
                    continue
                self.scoring_base_url = candidate
                print(f"Servicio scoring: {data.get('service', 'unknown')}")
                print(f"Version scoring: {data.get('version', 'unknown')}")
                print(f"Endpoint scoring activo: {self.scoring_base_url}")
                return True
            except Exception as exc:
                last_error = str(exc)

        print("ERROR: no se pudo conectar a scoring-core.")
        for candidate in self.scoring_candidates:
            print(f"  - {candidate}/health")
        if last_error:
            print(f"Ultimo error: {last_error}")
        print("Tip: exporta SCORING_CORE_API con la URL correcta, por ejemplo:")
        print("  SCORING_CORE_API=http://localhost:8097")
        return False

    def get_active_model(self) -> dict[str, Any] | None:
        try:
            params = {"client_id": self.client_id}
            if self.model_id:
                params["model_id"] = self.model_id
            resp = self.session.get(
                f"{self.scoring_base_url}/scoring/models/active",
                params=params,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            print(f"ERROR obteniendo modelo activo: {exc}")
        return None

    def validate_expected_model(self) -> bool:
        if not self.model_id:
            return True

        model = self.get_active_model()
        if not model:
            print("WARN: no se pudo resolver modelo activo para validar MODEL_ID; continuo sin bloquear.")
            return True

        active_model_id = str(model.get("modelId") or model.get("model_id") or "").strip().lower()
        expected_model_id = str(self.model_id).strip().lower()
        if active_model_id != expected_model_id:
            print(f"ERROR: MODEL_ID no coincide. Esperado={self.model_id} Activo={model.get('modelId')}")
            return False
        return True

    def send_chat(self, query_text: str) -> dict[str, Any] | None:
        metadata: dict[str, Any] = {
            "source": "tests/sandbox/dentist/simulate_chat_dentist.py",
        }
        if self.model_id:
            metadata["modelId"] = self.model_id

        payload: dict[str, Any] = {
            "client_id": self.client_id,
            "channel": self.channel,
            "channel_user_id": self.channel_user_id,
            "message_text": query_text,
            "metadata": metadata,
        }
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id
        if self.session_id:
            payload["session_id"] = self.session_id

        try:
            resp = self.session.post(
                f"{self.base_url}/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=45,
            )
            if resp.status_code != 200:
                print(f"ERROR {resp.status_code}: {resp.text[:800]}")
                return None

            data = resp.json()
            meta = data.get("meta") or {}
            normalized = {
                "leadId": str(meta.get("lead_id") or meta.get("leadId") or "").strip() or None,
                "conversationId": str(
                    meta.get("conversation_id")
                    or meta.get("conversationId")
                    or data.get("conversation_id")
                    or ""
                ).strip() or None,
                "sessionId": str(
                    data.get("session_id")
                    or meta.get("session_id")
                    or meta.get("sessionId")
                    or ""
                ).strip() or None,
                "scoringJobId": str(meta.get("scoringJobId") or meta.get("scoring_job_id") or "").strip() or None,
                "scoringStatus": str(meta.get("scoringStatus") or meta.get("scoring_status") or "").strip() or None,
                "answer": self._extract_chat_text(data),
                "components": data.get("components") or [],
                "scorecard": None,
                "scorecardId": None,
                "raw": data,
            }
            self.lead_id = normalized["leadId"] or self.lead_id
            self.conversation_id = normalized["conversationId"] or self.conversation_id
            self.session_id = normalized["sessionId"] or self.session_id
            self.last_scoring_job_id = normalized["scoringJobId"] or self.last_scoring_job_id
            return normalized
        except Exception as exc:
            print(f"ERROR en request: {exc}")
            return None

    def get_scorecard(self, lead_id: str) -> dict[str, Any] | None:
        try:
            resp = self.session.get(
                f"{self.scoring_base_url}/leads/{lead_id}/scorecards/latest",
                params={"client_id": self.client_id},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_scoring_job(self, job_id: str) -> dict[str, Any] | None:
        try:
            resp = self.session.get(f"{self.scoring_base_url}/scoring/jobs/{job_id}", timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _poll_latest_scorecard(
        self,
        lead_id: str,
        *,
        deadline: float,
        interval_seconds: float,
        settle_seconds: float,
    ) -> dict[str, Any] | None:
        last_seen = None
        stable_since = None
        fallback = None
        while time.time() < deadline:
            scorecard = self.get_scorecard(lead_id)
            if scorecard:
                fallback = scorecard
                extraction = scorecard.get("extractionResult", scorecard.get("extraction_result", {})) or {}
                signature = json.dumps(
                    {
                        "id": scorecard.get("id"),
                        "score": scorecard.get("scoreTotal", scorecard.get("score_total")),
                        "priority": scorecard.get("priorityLabel", scorecard.get("priority_label")),
                        "extraction": extraction,
                    },
                    sort_keys=True,
                )
                if signature != last_seen:
                    last_seen = signature
                    stable_since = time.time()
                elif stable_since and (time.time() - stable_since) >= settle_seconds:
                    return scorecard
            time.sleep(interval_seconds)
        return fallback

    def wait_for_latest_scorecard(
        self,
        max_wait_seconds: int = 90,
        interval_seconds: float = 1.5,
        settle_seconds: float = 5.0,
    ) -> dict[str, Any] | None:
        if self.last_scoring_job_id:
            deadline = time.time() + max_wait_seconds
            while time.time() < deadline:
                job_payload = self.get_scoring_job(self.last_scoring_job_id)
                if job_payload:
                    status = str(job_payload.get("status") or "").strip().lower()
                    if status == "completed":
                        lead_id = self.lead_id or str(job_payload.get("lead_id") or "").strip() or None
                        if lead_id:
                            self.lead_id = lead_id
                            latest = self._poll_latest_scorecard(
                                lead_id,
                                deadline=time.time() + min(30, max_wait_seconds),
                                interval_seconds=interval_seconds,
                                settle_seconds=settle_seconds,
                            )
                            if latest:
                                return latest
                        break
                    if status in {"failed", "cancelled", "degraded"}:
                        return None
                time.sleep(interval_seconds)

        if not self.lead_id:
            return None
        return self._poll_latest_scorecard(
            self.lead_id,
            deadline=time.time() + max_wait_seconds,
            interval_seconds=interval_seconds,
            settle_seconds=settle_seconds,
        )

    @staticmethod
    def display_scorebar(score: float, max_score: float = 10.0, width: int = 12) -> str:
        filled = int((score / max_score) * width)
        bar = "█" * filled + "░" * (width - filled)
        return bar

    def display_response(self, response: dict[str, Any], msg_num: int, query_text: str) -> None:
        print()
        print("=" * 67)
        print(f"[MENSAJE {msg_num}] \"{query_text[:50]}{'...' if len(query_text) > 50 else ''}\"")
        print("=" * 67)

        if not response:
            print("Sin respuesta")
            return

        lead_id = response.get("leadId")
        conversation_id = response.get("conversationId")
        session_id = response.get("sessionId")
        scoring_job_id = response.get("scoringJobId")
        scoring_status = response.get("scoringStatus")
        scorecard = response.get("scorecard")
        scorecard_id = response.get("scorecardId")
        answer = response.get("answer", "")

        print()
        print("RESPUESTA:")
        print(f"  leadId: {lead_id or '-'}")
        print(f"  conversationId: {conversation_id or '-'}")
        print(f"  sessionId: {session_id or '-'}")
        print(f"  scoringJobId: {scoring_job_id or '-'}")
        print(f"  scoringStatus: {scoring_status or '-'}")
        if scorecard_id:
            print(f"  scorecardId: {scorecard_id}")

        if scorecard:
            print()
            print("SCORECARD:", end=" ")
            model_version = scorecard.get("model_version", scorecard.get("modelVersion", "?"))
            prompt_version = scorecard.get("prompt_version", scorecard.get("promptVersion", "?"))
            print(f"(model v{model_version}, prompt v{prompt_version})")

            items = scorecard.get("score_items", scorecard.get("scoreItems", []))
            if items:
                print("  " + "-" * 49)
                print(f"  {'Criterio':<14} {'Score':>6} {'Barra':<14} {'Band':<8}")
                print("  " + "-" * 49)
                for item in items:
                    criterion = item.get("criterion_key", item.get("criterionKey", "?"))
                    score = item.get("score", 0)
                    band = item.get("band_key", item.get("bandKey", "-"))
                    bar = self.display_scorebar(score)
                    print(f"  {criterion:<14} {score:>6.2f} {bar:<14} {band:<8}")

                print("  " + "-" * 49)
                total = scorecard.get("score_total", scorecard.get("scoreTotal", 0))
                priority = scorecard.get("priority_label", scorecard.get("priorityLabel", "-"))
                print(f"  {'TOTAL':<14} {total:>6.2f} {'':<14} {priority:<8}")

            reasoning = scorecard.get("reasoning")
            if reasoning:
                print(f"\n  Reasoning: {reasoning}")

        print()
        print("AI RESPONSE:")
        print(f'  "{answer[:100]}{"..." if len(answer) > 100 else ""}"')
        print("-" * 67)

    def display_history(self) -> None:
        if not self.history:
            print("Sin historial de mensajes")
            return

        print()
        print("=" * 67)
        print("HISTORIAL DE MENSAJES")
        print("=" * 67)

        for i, entry in enumerate(self.history, 1):
            print(f"\n[{i}] {entry['query']}")
            print(f"    leadId: {entry.get('leadId', '-')}")
            print(f"    conversationId: {entry.get('conversationId', '-')}")
            print(f"    sessionId: {entry.get('sessionId', '-')}")
            print(f"    scoringJobId: {entry.get('scoringJobId', '-')}")
            print(f"    scorecardId: {entry.get('scorecardId', '-')}")
            if entry.get("scorecard"):
                total = entry["scorecard"].get("scoreTotal", entry["scorecard"].get("score_total", 0))
                priority = entry["scorecard"].get("priorityLabel", entry["scorecard"].get("priority_label", "-"))
                print(f"    score: {total:.2f} ({priority})")

    def display_db_queries(self) -> None:
        print()
        print("=" * 67)
        print("QUERIES SQL PARA VERIFICAR EN DB")
        print("=" * 67)

        if self.lead_id:
            print(f"""
-- Ver lead creado
SELECT id, full_name, current_scorecard_id, created_at
FROM lead_leads
WHERE id = '{self.lead_id}';

-- Ver scorecards del lead
SELECT id, score_total, priority_label, model_version, created_at
FROM lead_scorecards
WHERE lead_id = '{self.lead_id}'
ORDER BY created_at DESC;
""")

        if self.scorecards:
            latest = self.scorecards[-1]
            scorecard_id = latest.get("scorecard_id")
            if scorecard_id:
                print(f"""
-- Ver items del ultimo scorecard
SELECT criterion_key, score, band_id, explanation
FROM lead_score_items
WHERE scorecard_id = '{scorecard_id}';
""")

    def _append_history(self, response: dict[str, Any], query: str) -> None:
        self.history.append(
            {
                "query": query,
                "leadId": response.get("leadId"),
                "conversationId": response.get("conversationId"),
                "sessionId": response.get("sessionId"),
                "scoringJobId": response.get("scoringJobId"),
                "scorecardId": response.get("scorecardId"),
                "scorecard": response.get("scorecard"),
            }
        )

    def run_interactive(self) -> None:
        print()
        print("=" * 67)
        print("MODO INTERACTIVO - Simulador de Chat activo")
        print("=" * 67)
        print(f"Cliente: {self.client_id}")
        print(f"Chat API: {self.base_url}")
        print(f"Scoring API: {self.scoring_base_url}")
        print()

        if not self.check_health():
            print("ERROR: Servicio no disponible")
            return
        if not self.validate_expected_model():
            print("ERROR: Modelo esperado no activo para este cliente")
            return

        model = self.get_active_model()
        if model:
            print()
            print("Modelo de scoring activo:")
            print(f"  modelId: {model.get('modelId', model.get('model_id'))}")
            print(f"  version: {model.get('modelVersion', model.get('model_version'))}")
            criteria = model.get("criteria", [])
            if criteria:
                criterion_keys = [c.get("criterion_key", c.get("criterionKey")) for c in criteria]
                print(f"  criterios: {', '.join(filter(None, criterion_keys))}")

        print()
        print("Escribe un mensaje o 'exit' para terminar")
        print("-" * 67)

        msg_num = 0
        while True:
            try:
                user_input = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo...")
                break

            if not user_input:
                continue

            if user_input.lower() == "exit":
                break
            if user_input.lower() == "history":
                self.display_history()
                continue
            if user_input.lower() == "scorecard":
                latest = self.wait_for_latest_scorecard(max_wait_seconds=10)
                if latest:
                    print(json.dumps(latest, indent=2, ensure_ascii=False))
                else:
                    print("Sin scorecard")
                continue
            if user_input.lower() == "db":
                self.display_db_queries()
                continue
            if user_input.lower() == "reset":
                self.lead_id = None
                self.conversation_id = None
                self.session_id = None
                self.last_scoring_job_id = None
                self.history = []
                self.scorecards = []
                print("Conversacion reiniciada")
                continue

            msg_num += 1
            response = self.send_chat(user_input)
            if response:
                self._append_history(response, user_input)
                self.display_response(response, msg_num, user_input)

        self.display_summary()

    def run_auto(self) -> None:
        print()
        print("=" * 67)
        print("MODO AUTOMATICO - Simulador de Chat activo")
        print("=" * 67)
        print(f"Cliente: {self.client_id}")
        print(f"Chat API: {self.base_url}")
        print(f"Scoring API: {self.scoring_base_url}")
        print(f"Mensajes: {len(AUTO_MESSAGES)}")
        print()

        if not self.check_health():
            print("ERROR: Servicio no disponible")
            return
        if not self.validate_expected_model():
            print("ERROR: Modelo esperado no activo para este cliente")
            return

        model = self.get_active_model()
        if model:
            print()
            print(f"Modelo activo: v{model.get('model_version', model.get('modelVersion'))}")
            criteria = model.get("criteria", [])
            if criteria:
                criterion_keys = [c.get("criterion_key", c.get("criterionKey")) for c in criteria]
                print(f"Criterios: {', '.join(filter(None, criterion_keys))}")

        for i, query in enumerate(AUTO_MESSAGES, 1):
            response = self.send_chat(query)
            if response:
                self._append_history(response, query)
                self.display_response(response, i, query)

        self.display_summary()

    def run_single(self, query: str) -> None:
        print()
        print("=" * 67)
        print("MODO QUERY UNICA - Simulador de Chat activo")
        print("=" * 67)

        if not self.check_health():
            print("ERROR: Servicio no disponible")
            return
        if not self.validate_expected_model():
            print("ERROR: Modelo esperado no activo para este cliente")
            return

        response = self.send_chat(query)
        if response:
            self._append_history(response, query)
            self.display_response(response, 1, query)
            print()
            self.display_db_queries()

    def display_summary(self) -> None:
        print()
        print("=" * 67)
        print("RESUMEN DE SESION")
        print("=" * 67)

        print(f"\nMensajes enviados: {len(self.history)}")
        print(f"Lead ID: {self.lead_id or '-'}")
        print(f"Conversation ID: {self.conversation_id or '-'}")
        print(f"Session ID: {self.session_id or '-'}")
        print(f"Scoring Job ID: {self.last_scoring_job_id or '-'}")
        print(f"Scorecards cacheados: {len(self.scorecards)}")

        if self.lead_id or self.last_scoring_job_id:
            print("\nEsperando scorecard final (scoring async)...")
            latest = self.wait_for_latest_scorecard()
            if latest:
                latest_id = str(latest.get("id") or "").strip()
                if latest_id and not any(entry.get("scorecard_id") == latest_id for entry in self.scorecards):
                    self.scorecards.append(
                        {
                            "scorecard_id": latest_id,
                            "lead_id": self.lead_id,
                            "msg_num": len(self.history),
                            "query": "(scorecard final persistido)",
                            "scorecard": latest,
                        }
                    )

                print("Scorecard final persistido:")
                print(f"  id: {latest.get('id', '-')}")
                print(f"  score_total: {latest.get('scoreTotal', latest.get('score_total', '-'))}")
                print(f"  priority: {latest.get('priorityLabel', latest.get('priority_label', '-'))}")

                extraction = latest.get("extractionResult", latest.get("extraction_result", {})) or {}
                if extraction:
                    print("  extraction_result acumulado:")
                    for key in sorted(extraction.keys()):
                        print(f"    - {key}: {extraction[key]}")
            else:
                print("No se encontro scorecard final en el tiempo de espera.")

        if self.scorecards:
            print("\nEvolucion de scores:")
            for entry in self.scorecards:
                scorecard = entry.get("scorecard") or {}
                total = scorecard.get("score_total", scorecard.get("scoreTotal", 0))
                priority = scorecard.get("priority_label", scorecard.get("priorityLabel", "-"))
                print(f"  [{entry['msg_num']}] {total:.2f} ({priority}) - \"{entry['query'][:30]}...\"")

        self.display_db_queries()
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de flujo Chat activo -> Lead -> Scorecard")
    parser.add_argument("--auto", action="store_true", help="Ejecutar secuencia automatica de mensajes")
    parser.add_argument("--interactive", action="store_true", help="Iniciar sesion interactiva")
    parser.add_argument("--query", type=str, help="Enviar un solo mensaje")
    parser.add_argument("--client-id", type=str, default=CLIENT_ID, help=f"Client ID (default: {CLIENT_ID})")
    parser.add_argument(
        "--model-id",
        type=str,
        default=os.getenv("MODEL_ID"),
        help="Model ID esperado (opcional; por defecto usa el modelo configurado en BD para el cliente).",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("CHAT_WEB_RENDERER_URL", INFERENCE_V2_URL),
        help=f"URL del chat activo (default: env CHAT_WEB_RENDERER_URL o {INFERENCE_V2_URL})",
    )
    parser.add_argument(
        "--discover-endpoints",
        action="store_true",
        help="Intentar endpoints alternativos para chat y scoring (solo diagnostico).",
    )

    args = parser.parse_args()

    simulator = ChatSimulator(
        args.client_id,
        args.url,
        model_id=args.model_id,
        discover_endpoints=args.discover_endpoints,
    )

    if args.query:
        simulator.run_single(args.query)
    elif args.interactive:
        simulator.run_interactive()
    else:
        simulator.run_auto()


if __name__ == "__main__":
    main()
