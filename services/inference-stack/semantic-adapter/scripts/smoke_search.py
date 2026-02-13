import os

import httpx


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
CLIENT_ID = os.getenv("CLIENT_ID", "64f357a0-98eb-44f1-9f41-6e615ed26180")


def main() -> int:
    ok = True
    with httpx.Client(timeout=15.0) as client:
        health = client.get(f"{BASE_URL}/api/v1/health")
        print("GET /api/v1/health:", health.status_code)
        if health.status_code != 200:
            ok = False

        payload = {"query_text": "casas con piscina", "client_id": CLIENT_ID, "top_k": 3}
        search = client.post(f"{BASE_URL}/api/v1/search", json=payload)
        print("POST /api/v1/search:", search.status_code)
        if search.status_code != 200:
            ok = False
        else:
            body = search.json()
            print("results:", len(body.get("results", [])))

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
