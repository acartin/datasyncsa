#!/usr/bin/env python3
"""Sirve la web local y un API mínimo respaldado por Postgres."""

from __future__ import annotations

import argparse
import json
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from web_backend.catalog_db import (
    fetch_catalog_bundles_from_db,
    fetch_product_catalog_from_db,
    fetch_product_comparison_from_db,
)


class PriceScrapperWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        if self.path.startswith("/web/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/web/")
            self.end_headers()
            return

        if parsed.path in {"/web", "/web/"}:
            self.path = "/web/index.html"
            return super().do_GET()

        if parsed.path == "/api/catalog-bundles":
            return self._handle_catalog_bundles(parsed)
        if parsed.path == "/api/product-catalog":
            return self._handle_product_catalog(parsed)
        if parsed.path == "/api/product-comparison":
            return self._handle_product_comparison(parsed)

        return super().do_GET()

    def _handle_catalog_bundles(self, parsed) -> None:
        query = parse_qs(parsed.query)
        force_refresh = query.get("refresh", ["0"])[0] in {"1", "true", "yes"}
        try:
            payload = fetch_catalog_bundles_from_db(force_refresh=force_refresh)
            response = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
        except Exception as exc:  # pragma: no cover - defensive path
            response = json.dumps(
                {"error": str(exc), "path": parsed.path},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    def _handle_product_catalog(self, parsed) -> None:
        query = parse_qs(parsed.query)
        force_refresh = query.get("refresh", ["0"])[0] in {"1", "true", "yes"}
        try:
            payload = fetch_product_catalog_from_db(force_refresh=force_refresh)
            response = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
        except Exception as exc:  # pragma: no cover - defensive path
            response = json.dumps(
                {"error": str(exc), "path": parsed.path},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    def _handle_product_comparison(self, parsed) -> None:
        query = parse_qs(parsed.query)
        product_key_text = query.get("product_key", [""])[0].strip()
        ean = query.get("ean", [""])[0].strip() or None
        try:
            product_key = int(product_key_text) if product_key_text else None
        except ValueError:
            product_key = None

        try:
            payload = fetch_product_comparison_from_db(
                product_key=product_key,
                ean=ean,
            )
            response = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
        except Exception as exc:  # pragma: no cover - defensive path
            response = json.dumps(
                {"error": str(exc), "path": parsed.path},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sirve la web local de price-scrapper y un API respaldado por BD."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host de escucha. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Puerto HTTP. Default: 8765",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    handler = partial(PriceScrapperWebHandler, directory=str(SERVICE_DIR))
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Price Scrapper web disponible en http://{args.host}:{args.port}/web/", flush=True)
    print(
        f"API de bundles disponible en http://{args.host}:{args.port}/api/catalog-bundles",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
