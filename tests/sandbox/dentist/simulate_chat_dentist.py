#!/usr/bin/env python3
"""
Simulador de flujo Chat -> Lead -> Scorecard (v2)

Uso:
  python tests/sandbox/dentist/simulate_chat_dentist.py              # modo interactivo
  python tests/sandbox/dentist/simulate_chat_dentist.py --auto       # modo automatico
  python tests/sandbox/dentist/simulate_chat_dentist.py --query "Hola"  # mensaje unico

Compatibilidad:
  python tests/sandbox/simulate_chat_dentist.py  # wrapper legacy

Comandos interactivos:
  exit      - Terminar sesion
  history   - Ver historial de mensajes
  scorecard - Ver ultimo scorecard detallado
  db        - Mostrar queries SQL para verificar en DB
  reset     - Iniciar nueva conversacion
"""

import argparse
import json
import os
import sys
import time
from uuid import UUID
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: requests no esta instalado. Instala con: pip install requests")
    sys.exit(1)

CLIENT_ID = "66fc0a3b-c8d3-4707-8471-c751c642852d"
INFERENCE_V2_URL = "http://localhost:8091/api/v2"


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
        self.lead_id = None
        self.conversation_id = None
        self.history = []
        self.scorecards = []
        self.session = requests.Session()
        if discover_endpoints:
            self.candidate_urls = self._build_candidate_urls(self.base_url)
        else:
            self.candidate_urls = [self.base_url]

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        normalized = (url or "").strip().rstrip("/")
        if not normalized:
            normalized = INFERENCE_V2_URL
        if normalized.endswith("/api/v2"):
            return normalized
        if normalized.endswith("/api/v2/"):
            return normalized[:-1]
        if normalized.endswith("/api"):
            return f"{normalized}/v2"
        return f"{normalized}/api/v2"

    def _build_candidate_urls(self, explicit_url: str) -> list[str]:
        env_candidates = [
            os.getenv("INFERENCE_V2_API"),
            os.getenv("INFERENCE_V2_URL"),
        ]
        defaults = [
            explicit_url,
            "http://localhost:8091/api/v2",
            "http://127.0.0.1:8091/api/v2",
            "http://inference-core-v2:8000/api/v2",
        ]

        seen = set()
        candidates = []
        for raw in env_candidates + defaults:
            if not raw:
                continue
            normalized = self._normalize_base_url(raw)
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(normalized)
        return candidates
        
    def check_health(self) -> bool:
        last_error = None
        for candidate in self.candidate_urls:
            try:
                resp = self.session.get(f"{candidate}/health", timeout=10)
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}"
                    continue

                self.base_url = candidate
                data = resp.json()
                print(f"Servicio: {data.get('service', 'unknown')}")
                print(f"Version: {data.get('version', 'unknown')}")
                print(f"Cache: {data.get('cache', 'unknown')}")
                print(f"Endpoint activo: {self.base_url}")
                return True
            except Exception as e:
                last_error = str(e)

        print("ERROR: no se pudo conectar al API v2.")
        for candidate in self.candidate_urls:
            print(f"  - {candidate}/health")
        if last_error:
            print(f"Ultimo error: {last_error}")
        print("Tip: exporta INFERENCE_V2_API con la URL correcta, por ejemplo:")
        print("  INFERENCE_V2_API=http://localhost:8091/api/v2")
        return False
    
    def get_active_model(self) -> dict:
        try:
            params = {"client_id": self.client_id}
            # Parameter may be ignored by API, but keeps test intent explicit.
            if self.model_id:
                params["model_id"] = self.model_id

            resp = self.session.get(f"{self.base_url}/scoring/models/active", params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"ERROR obteniendo modelo activo: {e}")
        return None

    def validate_expected_model(self) -> bool:
        if not self.model_id:
            return True

        model = self.get_active_model()
        if not model:
            print("ERROR: no se pudo resolver modelo activo para validar MODEL_ID.")
            return False

        active_model_id = str(model.get("modelId") or model.get("model_id") or "").strip().lower()
        expected_model_id = str(self.model_id).strip().lower()
        if active_model_id != expected_model_id:
            print(f"ERROR: MODEL_ID no coincide. Esperado={self.model_id} Activo={model.get('modelId')}")
            return False
        return True
    
    def send_chat(self, query_text: str) -> dict:
        payload = {
            "queryText": query_text,
            "clientId": self.client_id,
            "userMetadata": {"modelId": self.model_id} if self.model_id else {},
        }
        if self.conversation_id:
            payload["conversationId"] = self.conversation_id
        
        try:
            resp = self.session.post(
                f"{self.base_url}/chat",
                json=payload,
                timeout=30
            )
            
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"ERROR {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            print(f"ERROR en request: {e}")
            return None
    
    def get_scorecard(self, lead_id: str) -> dict:
        try:
            resp = self.session.get(f"{self.base_url}/leads/{lead_id}/scorecards/latest", timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def wait_for_latest_scorecard(
        self,
        max_wait_seconds: int = 60,
        interval_seconds: float = 1.5,
        settle_seconds: float = 5.0,
    ) -> dict:
        """Poll latest scorecard endpoint until async scoring is persisted and stable."""
        if not self.lead_id:
            return None

        deadline = time.time() + max_wait_seconds
        last_seen = None
        stable_since = None
        fallback = None
        while time.time() < deadline:
            scorecard = self.get_scorecard(self.lead_id)
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
    
    def display_scorebar(self, score: float, max_score: float = 10.0, width: int = 12) -> str:
        filled = int((score / max_score) * width)
        bar = "█" * filled + "░" * (width - filled)
        return bar
    
    def display_response(self, response: dict, msg_num: int, query_text: str):
        print()
        print("=" * 67)
        print(f"[MENSAJE {msg_num}] \"{query_text[:50]}{'...' if len(query_text) > 50 else ''}\"")
        print("=" * 67)
        
        if not response:
            print("Sin respuesta")
            return
        
        lead_id = response.get("leadId")
        conversation_id = response.get("conversationId")
        scorecard = response.get("scorecard")
        scorecard_id = response.get("scorecardId")
        answer = response.get("answer", "")
        
        is_new_lead = lead_id and lead_id != self.lead_id
        self.lead_id = lead_id
        self.conversation_id = conversation_id
        
        if scorecard_id:
            self.scorecards.append({
                "scorecard_id": scorecard_id,
                "lead_id": lead_id,
                "msg_num": msg_num,
                "query": query_text,
                "scorecard": scorecard
            })
        
        print()
        print("RESPUESTA:")
        if is_new_lead:
            print(f"  leadId: {lead_id} (NUEVO)")
        else:
            print(f"  leadId: {lead_id}")
        print(f"  conversationId: {conversation_id}")
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
    
    def display_history(self):
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
            print(f"    scorecardId: {entry.get('scorecardId', '-')}")
            if entry.get("scorecard"):
                total = entry["scorecard"].get("scoreTotal", 0)
                priority = entry["scorecard"].get("priorityLabel", "-")
                print(f"    score: {total:.2f} ({priority})")
    
    def display_db_queries(self):
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
            print(f"""
-- Ver items del ultimo scorecard
SELECT criterion_key, score, band_id, explanation
FROM lead_score_items
WHERE scorecard_id = '{scorecard_id}';
""")
    
    def run_interactive(self):
        print()
        print("=" * 67)
        print("MODO INTERACTIVO - Simulador de Chat Flow v2")
        print("=" * 67)
        print(f"Cliente: {self.client_id}")
        print(f"API: {self.base_url}")
        print()
        
        if not self.check_health():
            print("ERROR: Servicio no disponible")
            return
        if not self.validate_expected_model():
            print("ERROR: Modelo esperado no activo para este cliente")
            return
        
        print()
        model = self.get_active_model()
        if model:
            print("Modelo de scoring activo:")
            print(f"  modelId: {model.get('modelId')}")
            print(f"  version: {model.get('modelVersion')}")
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
            elif user_input.lower() == "history":
                self.display_history()
                continue
            elif user_input.lower() == "scorecard":
                if self.scorecards:
                    latest = self.scorecards[-1]
                    print(json.dumps(latest["scorecard"], indent=2, ensure_ascii=False))
                else:
                    print("Sin scorecards")
                continue
            elif user_input.lower() == "db":
                self.display_db_queries()
                continue
            elif user_input.lower() == "reset":
                self.lead_id = None
                self.conversation_id = None
                self.history = []
                self.scorecards = []
                print("Conversacion reiniciada")
                continue
            
            msg_num += 1
            response = self.send_chat(user_input)
            
            if response:
                self.history.append({
                    "query": user_input,
                    "leadId": response.get("leadId"),
                    "conversationId": response.get("conversationId"),
                    "scorecardId": response.get("scorecardId"),
                    "scorecard": response.get("scorecard")
                })
                self.display_response(response, msg_num, user_input)
        
        self.display_summary()
    
    def run_auto(self):
        print()
        print("=" * 67)
        print("MODO AUTOMATICO - Simulador de Chat Flow v2")
        print("=" * 67)
        print(f"Cliente: {self.client_id}")
        print(f"API: {self.base_url}")
        print(f"Mensajes: {len(AUTO_MESSAGES)}")
        print()
        
        if not self.check_health():
            print("ERROR: Servicio no disponible")
            return
        if not self.validate_expected_model():
            print("ERROR: Modelo esperado no activo para este cliente")
            return
        
        print()
        model = self.get_active_model()
        if model:
            print(f"Modelo activo: v{model.get('model_version', model.get('modelVersion'))}")
            criteria = model.get("criteria", [])
            if criteria:
                criterion_keys = [c.get("criterion_key", c.get("criterionKey")) for c in criteria]
                print(f"Criterios: {', '.join(filter(None, criterion_keys))}")
        
        for i, query in enumerate(AUTO_MESSAGES, 1):
            response = self.send_chat(query)
            
            if response:
                self.history.append({
                    "query": query,
                    "leadId": response.get("leadId"),
                    "conversationId": response.get("conversationId"),
                    "scorecardId": response.get("scorecardId"),
                    "scorecard": response.get("scorecard")
                })
                self.display_response(response, i, query)
            
        self.display_summary()
    
    def run_single(self, query: str):
        print()
        print("=" * 67)
        print("MODO QUERY UNICA - Simulador de Chat Flow v2")
        print("=" * 67)
        
        if not self.check_health():
            print("ERROR: Servicio no disponible")
            return
        if not self.validate_expected_model():
            print("ERROR: Modelo esperado no activo para este cliente")
            return
        
        response = self.send_chat(query)
        if response:
            self.display_response(response, 1, query)
            print()
            self.display_db_queries()
    
    def display_summary(self):
        print()
        print("=" * 67)
        print("RESUMEN DE SESION")
        print("=" * 67)
        
        print(f"\nMensajes enviados: {len(self.history)}")
        print(f"Lead ID: {self.lead_id or '-'}")
        print(f"Conversation ID: {self.conversation_id or '-'}")
        print(f"Scorecards generados: {len(self.scorecards)}")

        if self.lead_id:
            print("\nEsperando scorecard final (scoring async)...")
            latest = self.wait_for_latest_scorecard()
            if latest:
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
                total = entry["scorecard"].get("score_total", entry["scorecard"].get("scoreTotal", 0))
                priority = entry["scorecard"].get("priority_label", entry["scorecard"].get("priorityLabel", "-"))
                print(f"  [{entry['msg_num']}] {total:.2f} ({priority}) - \"{entry['query'][:30]}...\"")
        
        self.display_db_queries()
        print()


def main():
    parser = argparse.ArgumentParser(description="Simulador de flujo Chat -> Lead -> Scorecard v2")
    parser.add_argument("--auto", action="store_true", help="Ejecutar secuencia automatica de mensajes")
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
        default=os.getenv("INFERENCE_V2_API", INFERENCE_V2_URL),
        help=f"URL del API v2 (default: env INFERENCE_V2_API o {INFERENCE_V2_URL})",
    )
    parser.add_argument(
        "--discover-endpoints",
        action="store_true",
        help="Intentar endpoints alternativos (solo para diagnostico). Por defecto usa modo estricto.",
    )
    
    args = parser.parse_args()
    
    simulator = ChatSimulator(
        args.client_id,
        args.url,
        model_id=args.model_id,
        discover_endpoints=args.discover_endpoints
    )
    
    if args.query:
        simulator.run_single(args.query)
    elif args.auto:
        simulator.run_auto()
    else:
        simulator.run_auto()


if __name__ == "__main__":
    main()
