#!/usr/bin/env python3
"""
Test End-to-End del flujo Chat + Scoring V2 (RAG híbrido).

Uso:
  python tests/system/test_chat_e2e.py

Variables opcionales:
  INFERENCE_V2_API   (default: http://localhost:8091/api/v2)
  CLIENT_ID          (default: 019b4872-51f6-72d3-84c9-45183ff700d0)
  E2E_WAIT_SECONDS   (default: 20)
"""
import os
import requests
import json
import sys
import time

INFERENCE_V2_API = os.getenv("INFERENCE_V2_API", "http://localhost:8091/api/v2").rstrip("/")
CLIENT_ID = os.getenv("CLIENT_ID", "019b4872-51f6-72d3-84c9-45183ff700d0")
E2E_WAIT_SECONDS = int(os.getenv("E2E_WAIT_SECONDS", "20"))


def wait_for_scorecard(lead_id: str, timeout_seconds: int) -> dict | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{INFERENCE_V2_API}/leads/{lead_id}/scorecards/latest",
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        time.sleep(1.5)
    return None

def test_chat_flow():
    print("Test End-to-End: Inference Core V2 Chat")
    print("=" * 60)

    # 0) Health check
    health = requests.get(f"{INFERENCE_V2_API}/health", timeout=10)
    print("Health status:", health.status_code)
    if health.status_code != 200:
        print("ERROR health:", health.text)
        return False

    # 1) Chat
    payload = {
        "queryText": "Hola, quiero opciones de propiedades de 2 habitaciones.",
        "clientId": CLIENT_ID,
        "filters": {"category": "property"}
    }

    print("\nEndpoint:", f"{INFERENCE_V2_API}/chat")
    print("Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    try:
        print("\nEnviando request de chat...")
        response = requests.post(
            f"{INFERENCE_V2_API}/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print("\nStatus Code:", response.status_code)
        if response.status_code != 200:
            print("ERROR:", response.text)
            return False

        data = response.json()
        print("\nRespuesta chat OK")
        print("conversationId:", data.get("conversationId"))
        print("leadId:", data.get("leadId"))
        print("answer:", (data.get("answer") or "")[:180])

        conversation_id = data.get("conversationId")
        lead_id = data.get("leadId")

        if not conversation_id or not lead_id:
            print("ERROR: faltan conversationId/leadId en respuesta")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return False

        # 2) Scorecard eventual (background)
        print(f"\nEsperando scorecard hasta {E2E_WAIT_SECONDS}s...")
        scorecard = wait_for_scorecard(lead_id, E2E_WAIT_SECONDS)
        if not scorecard:
            print("ERROR: no se obtuvo scorecard en el tiempo esperado")
            return False

        print("Scorecard OK")
        print("score_total:", scorecard.get("scoreTotal"))
        print("priority_label:", scorecard.get("priorityLabel"))

        return True

    except Exception as e:
        print("\nERROR:", str(e))
        return False

if __name__ == "__main__":
    success = test_chat_flow()
    sys.exit(0 if success else 1)
