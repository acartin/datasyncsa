import os

import httpx


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
CLIENT_ID = os.getenv("CLIENT_ID", "64f357a0-98eb-44f1-9f41-6e615ed26180")


def main() -> int:
    ok = True
    with httpx.Client(timeout=20.0) as client:
        health = client.get(f"{BASE_URL}/health")
        print("GET /health:", health.status_code)
        if health.status_code != 200:
            ok = False

        init_res = client.post(f"{BASE_URL}/chat/init", json={"client_id": CLIENT_ID})
        print("POST /chat/init:", init_res.status_code)
        if init_res.status_code != 200:
            ok = False

        chat_payload = {"text": "Hola", "client_id": CLIENT_ID}
        chat_res = client.post(f"{BASE_URL}/chat", json=chat_payload)
        print("POST /chat:", chat_res.status_code)
        if chat_res.status_code != 200:
            ok = False
        else:
            body = chat_res.json()
            print("session_id:", body.get("session_id"))

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
