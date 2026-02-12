#!/usr/bin/env python3
"""
Test End-to-End del flujo de Chat RAG
Ejecutar desde DENTRO de la red Docker para acceder a inference-core:8003
"""
import requests
import json
import sys

# Configuración - Endpoint interno de Docker
INFERENCE_CORE_API = "http://inference-core:8003/api/v1/chat"
CLIENT_ID = "019b4872-51f6-72d3-84c9-45183ff700d0"

def test_chat_flow():
    print("🧪 Test End-to-End: Inference Core Chat\n")
    print("=" * 60)
    
    # Payload de prueba
    payload = {
        "queryText": "¿Cuáles son los requisitos para solicitar un crédito hipotecario?",
        "clientId": CLIENT_ID,
        "filters": {
            "category": "RH"
        }
    }
    
    print(f"\n📤 Endpoint: {INFERENCE_CORE_API}")
    print(f"📋 Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("\n" + "=" * 60)
    
    try:
        print("\n⏳ Esperando respuesta...")
        response = requests.post(
            INFERENCE_CORE_API,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"\n📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ RESPUESTA EXITOSA\n")
            print("=" * 60)
            
            if "answer" in data:
                print(f"\n💬 Respuesta del Bot:")
                print(f"{data['answer']}\n")
            
            if "conversationId" in data:
                print(f"🆔 Conversation ID: {data['conversationId']}")
            
            if "sources" in data and data["sources"]:
                print(f"\n📚 Fuentes ({len(data['sources'])} documentos):")
                for i, source in enumerate(data["sources"], 1):
                    print(f"\n  {i}. {source.get('title', 'Sin título')}")
                    print(f"     Score: {source.get('score', 'N/A')}")
            
            print("\n" + "=" * 60)
            print("\n📄 JSON Completo:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            return True
        else:
            print(f"\n❌ ERROR: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_chat_flow()
    sys.exit(0 if success else 1)
