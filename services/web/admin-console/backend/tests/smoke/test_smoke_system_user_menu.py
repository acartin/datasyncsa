import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Set, Tuple

import httpx


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


BASE_URL = env("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SYSTEM_USER_EMAIL = env("SYSTEM_USER_EMAIL")
SYSTEM_USER_PASSWORD = env("SYSTEM_USER_PASSWORD")
EXPECTED_MENU_LINKS_RAW = env("EXPECTED_MENU_LINKS")
EXPECTED_MENU_LINKS = {item.strip() for item in EXPECTED_MENU_LINKS_RAW.split(",")} if EXPECTED_MENU_LINKS_RAW else set()


@dataclass(frozen=True)
class CheckResult:
    path: str
    status: int
    note: str = ""


def login(client: httpx.Client, email: str, password: str) -> str:
    response = client.post(
        f"{BASE_URL}/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Login failed for system-user: HTTP {response.status_code} - {response.text[:200]}")
    token = response.json().get("access_token", "")
    if not token:
        raise RuntimeError("Login succeeded but access_token is empty")
    return token


def iter_menu_links(items: Iterable[Dict[str, Any]]) -> Iterable[str]:
    for item in items:
        link = item.get("link")
        if isinstance(link, str) and link.startswith("/"):
            yield link
        sub_items = item.get("subItems") or []
        if isinstance(sub_items, list):
            yield from iter_menu_links(sub_items)


def extract_sdui_get_urls(payload: Any) -> Set[str]:
    urls: Set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            data_url = node.get("data_url")
            if isinstance(data_url, str) and data_url.startswith("/"):
                urls.add(data_url)

            source = node.get("source")
            if isinstance(source, str) and source.startswith("/"):
                urls.add(source)

            # Only follow explicit navigation actions for GET checks.
            if node.get("action") == "navigate":
                action_url = node.get("action_url")
                if isinstance(action_url, str) and action_url.startswith("/"):
                    urls.add(action_url)

            for value in node.values():
                walk(value)
            return

        if isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return {u for u in urls if "{" not in u and "}" not in u}


def get_json(client: httpx.Client, path: str, headers: Dict[str, str]) -> Tuple[int, Any]:
    response = client.get(f"{BASE_URL}{path}", headers=headers)
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return response.status_code, None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    return response.status_code, payload


def main() -> int:
    if not SYSTEM_USER_EMAIL or not SYSTEM_USER_PASSWORD:
        print("FAIL: define SYSTEM_USER_EMAIL and SYSTEM_USER_PASSWORD in env to run this smoke test.")
        return 1

    results: List[CheckResult] = []
    ok = True

    with httpx.Client(timeout=15.0) as client:
        token = login(client, SYSTEM_USER_EMAIL, SYSTEM_USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}

        status, app_init = get_json(client, "/app-init", headers)
        results.append(CheckResult(path="/app-init", status=status))
        if status != 200 or not isinstance(app_init, dict):
            print("FAIL: /app-init is unavailable for system-user")
            for row in results:
                print(f"{row.path}: {row.status} {row.note}".rstrip())
            return 1

        menu_items = (app_init.get("sidebar") or {}).get("items") or []
        if not isinstance(menu_items, list) or not menu_items:
            print("FAIL: /app-init returned no sidebar menu items for system-user")
            return 1

        to_visit: Set[str] = set(iter_menu_links(menu_items))
        if EXPECTED_MENU_LINKS:
            missing_menu_links = sorted(EXPECTED_MENU_LINKS - to_visit)
            if missing_menu_links:
                print(f"FAIL: menu is missing expected links: {missing_menu_links}")
                return 1
        visited: Set[str] = set()

        while to_visit:
            path = sorted(to_visit)[0]
            to_visit.remove(path)
            if path in visited:
                continue
            visited.add(path)

            status, payload = get_json(client, path, headers)
            note = ""
            if status == 200 and payload is None:
                note = "(non-json payload)"
            results.append(CheckResult(path=path, status=status, note=note))

            if status != 200 or payload is None:
                ok = False
                continue

            if isinstance(payload, dict):
                discovered = extract_sdui_get_urls(payload)
                for discovered_path in discovered:
                    if discovered_path not in visited:
                        to_visit.add(discovered_path)

        print("SYSTEM-USER MENU SMOKE")
        print(f"checked_paths={len(results)}")
        for row in sorted(results, key=lambda x: x.path):
            print(f"{row.path}: {row.status} {row.note}".rstrip())

        for row in results:
            if row.status >= 400:
                ok = False

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
