#!/usr/bin/env python3
"""Discovery de locations para cadenas VTEX usando el store-selector publico."""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from math import ceil
from typing import Any

from etl.chain_runtime_db import load_vtex_location_runtime_config
from etl.http_client import BrowserResponse, BrowserSession, create_browser_session, request_with_retry
from etl.postgres_cli import parse_env


REQUEST_TIMEOUT = 30
COUNTRY_CODE = "CRI"

BUNDLE_URL_PATTERN = re.compile(r'https://[^"\']+\.js[^"\']*store-selector@[^"\']*')
POSTAL_CODE_PATTERN = re.compile(r'postalCode:"(\d{5})"')


@dataclass(frozen=True)
class VtexLocationChainConfig:
    chain_id: str
    base_url: str
    display_name: str
    sales_channel: str | None = None


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_chain_runtime_config(chain_id: str) -> VtexLocationChainConfig:
    payload = load_vtex_location_runtime_config(parse_env(), chain_id)
    return VtexLocationChainConfig(
        chain_id=chain_id,
        base_url=str(payload.get("base_url") or "").strip(),
        display_name=str(payload.get("display_name") or chain_id).strip(),
        sales_channel=normalize_string(payload.get("sales_channel")),
    )


class VtexLocationScraper:
    def __init__(
        self,
        *,
        config: VtexLocationChainConfig,
        sleep_min: float = 0.80,
        sleep_max: float = 1.80,
        postal_code_limit: int | None = None,
    ) -> None:
        self.config = config
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self.postal_code_limit = postal_code_limit
        self.request_counter = 0
        self.session = self._build_session()

    def _build_session(self) -> BrowserSession:
        return create_browser_session(
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": f"{self.config.base_url}/",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
                ),
            }
        )

    def _sleep_if_needed(self) -> None:
        if self.request_counter <= 0:
            return
        time.sleep(random.uniform(self.sleep_min, self.sleep_max))

    def _get(self, url: str, **kwargs: Any) -> BrowserResponse:
        self._sleep_if_needed()
        response = request_with_retry(
            self.session,
            "GET",
            url,
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        self.request_counter += 1
        response.raise_for_status()
        return response

    def fetch_homepage_html(self) -> str:
        return self._get(f"{self.config.base_url}/").text

    def extract_bundle_url(self, homepage_html: str) -> str:
        match = BUNDLE_URL_PATTERN.search(homepage_html)
        if not match:
            raise RuntimeError(
                f"No pude encontrar la bundle de store-selector para {self.config.chain_id!r}."
            )
        return match.group(0)

    def fetch_bundle_text(self, bundle_url: str) -> str:
        return self._get(bundle_url).text

    def resolve_sales_channel(self, bundle_text: str) -> str:
        if self.config.sales_channel:
            return self.config.sales_channel

        regions_idx = bundle_text.find("/api/checkout/pub/regions?country=")
        if regions_idx >= 0:
            snippet = bundle_text[regions_idx : regions_idx + 300]
            match = re.search(r'concat\((\d+),"&postalCode=', snippet)
            if match:
                return match.group(1)

        order_form = self._get(f"{self.config.base_url}/api/checkout/pub/orderForm/").json()
        sales_channel = normalize_string(order_form.get("salesChannel"))
        if sales_channel:
            return sales_channel

        raise RuntimeError(
            f"No pude determinar sales_channel para {self.config.chain_id!r}."
        )

    def extract_postal_codes(self, bundle_text: str) -> list[str]:
        postal_codes = sorted(set(POSTAL_CODE_PATTERN.findall(bundle_text)))
        if self.postal_code_limit is not None:
            return postal_codes[: self.postal_code_limit]
        return postal_codes

    def fetch_region_sellers(self, *, sales_channel: str, postal_code: str) -> list[dict[str, Any]]:
        response = self._get(
            f"{self.config.base_url}/api/checkout/pub/regions",
            params={
                "country": COUNTRY_CODE,
                "sc": sales_channel,
                "postalCode": postal_code,
            },
        )
        payload = response.json()
        if not isinstance(payload, list):
            return []
        return payload

    def classify_location_type(
        self,
        *,
        seller_id: str,
        seller_name: str,
        observed_postal_codes_count: int,
        total_postal_codes: int,
    ) -> tuple[str, str]:
        normalized = seller_name.upper()
        generic_coverage_threshold = max(75, ceil(total_postal_codes * 0.35))

        if "BODEGA" in normalized:
            return ("distribution_store", "name_contains_bodega")
        if "STORE" in normalized:
            return ("distribution_store", "name_contains_store")
        if seller_name.strip() == seller_id.strip():
            return ("distribution_store", "name_equals_source_id")
        if observed_postal_codes_count >= generic_coverage_threshold:
            return ("distribution_store", "broad_postal_code_coverage")
        return ("physical_store", "store_specific_name")

    def discover_locations(self) -> list[dict[str, Any]]:
        homepage_html = self.fetch_homepage_html()
        bundle_url = self.extract_bundle_url(homepage_html)
        bundle_text = self.fetch_bundle_text(bundle_url)
        sales_channel = self.resolve_sales_channel(bundle_text)
        postal_codes = self.extract_postal_codes(bundle_text)

        discovered: dict[str, dict[str, Any]] = {}
        total_postal_codes = len(postal_codes)
        print(
            f"[{self.config.chain_id}] sales_channel={sales_channel} | postal_codes={total_postal_codes}",
            flush=True,
        )

        for index, postal_code in enumerate(postal_codes, start=1):
            regions = self.fetch_region_sellers(sales_channel=sales_channel, postal_code=postal_code)
            for region in regions:
                region_id = normalize_string(region.get("id"))
                for seller in region.get("sellers") or []:
                    seller_id = normalize_string(seller.get("id"))
                    seller_name = normalize_string(seller.get("name")) or seller_id
                    if not seller_id or not seller_name:
                        continue

                    row = discovered.setdefault(
                        seller_id,
                        {
                            "chain_id": self.config.chain_id,
                            "location_code": seller_id,
                            "source_engine": "vtex",
                            "source_location_ref": seller_id,
                            "source_internal_id": None,
                            "location_name": seller_name,
                            "location_type": "physical_store",
                            "sales_channel": sales_channel,
                            "region_id": region_id,
                            "address_text": None,
                            "province": None,
                            "canton": None,
                            "district": None,
                            "postal_code": postal_code,
                            "latitude": None,
                            "longitude": None,
                            "phone": None,
                            "is_default": False,
                            "source_origin": "engine_api",
                            "_observed_postal_codes": set(),
                            "_observed_region_ids": set(),
                            "_sample_payload": seller,
                            "_bundle_url": bundle_url,
                        },
                    )
                    row["_observed_postal_codes"].add(postal_code)
                    if region_id:
                        row["_observed_region_ids"].add(region_id)

            if index == total_postal_codes or index % 50 == 0:
                print(
                    f"[{self.config.chain_id}] postal_codes procesados: {index}/{total_postal_codes} | "
                    f"locations={len(discovered)}",
                    flush=True,
                )

        locations: list[dict[str, Any]] = []
        for row in discovered.values():
            observed_postal_codes = sorted(row.pop("_observed_postal_codes"))
            observed_region_ids = sorted(row.pop("_observed_region_ids"))
            observed_postal_codes_count = len(observed_postal_codes)
            location_type, location_type_reason = self.classify_location_type(
                seller_id=str(row["source_location_ref"]),
                seller_name=str(row["location_name"]),
                observed_postal_codes_count=observed_postal_codes_count,
                total_postal_codes=total_postal_codes,
            )
            row["location_type"] = location_type
            source_payload = {
                "bundle_url": row.pop("_bundle_url"),
                "sample_seller_payload": row.pop("_sample_payload"),
                "observed_postal_codes_count": observed_postal_codes_count,
                "observed_postal_codes_sample": observed_postal_codes[:25],
                "observed_region_ids": observed_region_ids,
                "postal_code_universe_count": total_postal_codes,
                "location_type_reason": location_type_reason,
            }
            row["source_payload"] = source_payload
            locations.append(row)

        locations.sort(key=lambda item: (item["location_type"], item["location_name"]))
        return locations


def discover_locations(
    chain_id: str,
    *,
    sleep_min: float = 0.80,
    sleep_max: float = 1.80,
    postal_code_limit: int | None = None,
) -> list[dict[str, Any]]:
    scraper = VtexLocationScraper(
        config=load_chain_runtime_config(chain_id),
        sleep_min=sleep_min,
        sleep_max=sleep_max,
        postal_code_limit=postal_code_limit,
    )
    return scraper.discover_locations()
