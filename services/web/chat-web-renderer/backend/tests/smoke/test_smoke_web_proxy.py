import json
import os
import urllib.error
import urllib.request


BASE_URL = os.getenv("BASE_URL", "http://chat-web-renderer-ui").rstrip("/")
CLIENT_ID = os.getenv("CLIENT_ID", "64f357a0-98eb-44f1-9f41-6e615ed26180")


def post_json(path: str, payload: dict):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8"), resp.headers.get("Content-Type", "")


def main() -> int:
    ok = True

    try:
        status, body, ctype = post_json("/api/chat/init", {"client_id": CLIENT_ID})
        print("POST /api/chat/init:", status, ctype)
        if status != 200 or "application/json" not in ctype:
            ok = False
        else:
            parsed = json.loads(body)
            if "branding" not in parsed:
                ok = False
    except urllib.error.HTTPError as exc:
        print("POST /api/chat/init HTTPError:", exc.code)
        ok = False
    except Exception as exc:
        print("POST /api/chat/init Exception:", str(exc))
        ok = False

    try:
        status, body, ctype = post_json("/api/chat", {"text": "hola", "client_id": CLIENT_ID})
        print("POST /api/chat:", status, ctype)
        if status != 200 or "application/json" not in ctype:
            ok = False
    except urllib.error.HTTPError as exc:
        print("POST /api/chat HTTPError:", exc.code)
        ok = False
    except Exception as exc:
        print("POST /api/chat Exception:", str(exc))
        ok = False

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
