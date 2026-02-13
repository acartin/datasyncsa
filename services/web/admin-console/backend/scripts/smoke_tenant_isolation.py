import os
import sys
from typing import Dict, List, Tuple

import httpx


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


BASE_URL = env("BASE_URL", "http://127.0.0.1:8000").rstrip("/")

USERS: List[Tuple[str, str, str]] = [
    (
        env("SUPERADMIN_EMAIL", "acartina15@hotmail.com"),
        env("SUPERADMIN_PASSWORD", "Techimi.15"),
        "superadmin",
    ),
    (
        env("COCA_ADMIN_EMAIL", "cocacola-admin@cocacola.com"),
        env("COCA_ADMIN_PASSWORD", "holalola"),
        "coca_admin",
    ),
    (
        env("PEPSI_ADMIN_EMAIL", "pepsi-admin@pepsi.com"),
        env("PEPSI_ADMIN_PASSWORD", "holalola"),
        "pepsi_admin",
    ),
]

CHECK_PATHS = ["/app-init", "/leads/me", "/prompts", "/ai-library", "/contacts?limit=5"]


def login(client: httpx.Client, email: str, password: str) -> Tuple[int, str]:
    response = client.post(
        f"{BASE_URL}/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = ""
    if response.status_code == 200:
        token = response.json().get("access_token", "")
    return response.status_code, token


def main() -> int:
    ok = True
    sessions: Dict[str, str] = {}

    with httpx.Client(timeout=10.0) as client:
        for email, password, label in USERS:
            status, token = login(client, email, password)
            print(f"LOGIN {label}: {status}")
            if status != 200:
                ok = False
                continue
            sessions[label] = token

        for label, token in sessions.items():
            headers = {"Authorization": f"Bearer {token}"}
            print(f"\nSESSION {label}")
            for path in CHECK_PATHS:
                response = client.get(f"{BASE_URL}{path}", headers=headers)
                print(f"{path}: {response.status_code}")
                if response.status_code != 200:
                    ok = False

        for label in ("coca_admin", "pepsi_admin", "superadmin"):
            token = sessions.get(label)
            if not token:
                continue
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get(f"{BASE_URL}/prompts/data", headers=headers)
            if response.status_code != 200:
                print(f"PROMPTS_SCOPE {label}: HTTP {response.status_code}")
                ok = False
                continue
            data = response.json()
            client_ids = sorted({str(item.get("client_id")) for item in data if item.get("client_id")})
            print(f"PROMPTS_SCOPE {label}: count={len(data)} client_ids={client_ids}")
            if label in ("coca_admin", "pepsi_admin") and len(client_ids) != 1:
                ok = False

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
