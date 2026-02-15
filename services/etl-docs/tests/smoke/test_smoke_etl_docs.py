import os
import uuid
import urllib.error
import urllib.request


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def get_status(path: str) -> int:
    req = urllib.request.Request(f"{BASE_URL}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def main() -> int:
    ok = True

    root = get_status("/")
    print("GET /:", root)
    ok = ok and root == 200

    invalid_list = get_status("/documents/list/not-a-uuid")
    print("GET /documents/list/not-a-uuid:", invalid_list)
    ok = ok and invalid_list == 400

    list_status = get_status(f"/documents/list/{uuid.uuid4()}")
    print("GET /documents/list/{client_id}:", list_status)
    ok = ok and list_status == 200

    job_status = get_status("/documents/jobs/job_does_not_exist")
    print("GET /documents/jobs/{job_id}:", job_status)
    ok = ok and job_status == 404

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
