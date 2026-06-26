#!/usr/bin/env python3
"""Discovery de sucursales para Instaleap usando pagina publica + mapa KML + API v2."""

from __future__ import annotations

import html
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from difflib import SequenceMatcher
from html.parser import HTMLParser
from typing import Any

import urllib3

from etl.chain_runtime_db import load_instaleap_location_runtime_config
from etl.http_client import BrowserSession, create_browser_session, request_with_retry, set_rate_limiter
from etl.postgres_cli import parse_env


REQUEST_TIMEOUT = 30
GRAPHQL_TIMEOUT = 30
SOURCE_URL = "https://info.megasuper.com/Sucursales.html"
SOURCE_MAP_KML_URL = (
    "https://www.google.com/maps/d/kml?mid=1xQs8V5yx7O0iAHlTl5WXix4Qi3xgKVz1&forcekml=1"
)
STORES_NEARBY_QUERY = """
query GetStoresNearbyByCoords(
  $clientId: String!
  $operationalModel: OperationModel!
  $coordinates: Coords!
) {
  getStoresNearbyByCoords(
    clientId: $clientId
    operationalModel: $operationalModel
    coordinates: $coordinates
  ) {
    id
    name
    code
    phone
    state
    cities {
      name
    }
    address
    country
    dynamicParams
    operationModel
    serviceFee {
      PICK_AND_COLLECT
      DELIVERY
    }
    usedIfNotCoverage
  }
}
""".strip()
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def normalize_name_for_match(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("\xa0", " ").lower()
    text = re.sub(r"\bmega\s*super\b", "megasuper", text)
    text = re.sub(r"\bmegasuper\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def similarity_score(left: str | None, right: str | None) -> float:
    normalized_left = normalize_name_for_match(left)
    normalized_right = normalize_name_for_match(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


@dataclass(frozen=True)
class InstaleapLocationChainConfig:
    chain_id: str
    display_name: str
    client_id: str
    graphql_v2_endpoint: str
    default_store_reference: str | None = None
    default_store_internal_id: str | None = None


@dataclass(frozen=True)
class KmlPlacemark:
    name: str
    latitude: float
    longitude: float
    description: str | None = None


def load_chain_runtime_config(chain_id: str) -> InstaleapLocationChainConfig:
    payload = load_instaleap_location_runtime_config(parse_env(), chain_id)
    client_id = normalize_string(payload.get("client_id"))
    if not client_id:
        raise RuntimeError(f"Falta client_id para chain_id={chain_id!r} en runtime de Instaleap.")
    graphql_v2_endpoint = normalize_string(payload.get("graphql_v2_endpoint"))
    if not graphql_v2_endpoint:
        raise RuntimeError(
            f"Falta graphql_v2_endpoint para chain_id={chain_id!r} en runtime de Instaleap."
        )
    return InstaleapLocationChainConfig(
        chain_id=chain_id,
        display_name=str(payload.get("display_name") or chain_id).strip(),
        client_id=client_id,
        graphql_v2_endpoint=graphql_v2_endpoint,
        default_store_reference=normalize_string(payload.get("default_store_reference")),
        default_store_internal_id=normalize_string(payload.get("default_store_internal_id")),
    )


class SucursalesHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current_province: str | None = None
        self.capture_h3 = False
        self.capture_p = False
        self.buffer: list[str] = []
        self.entries: list[tuple[str | None, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h3":
            self.capture_h3 = True
            self.buffer = []
        elif tag == "p":
            self.capture_p = True
            self.buffer = []
        elif tag == "br" and self.capture_p:
            self.buffer.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self.capture_h3:
            heading = self._clean("".join(self.buffer))
            if heading:
                self.current_province = heading
            self.capture_h3 = False
            self.buffer = []
        elif tag == "p" and self.capture_p:
            paragraph = self._clean("".join(self.buffer))
            if paragraph and paragraph.lower().startswith("megasuper "):
                self.entries.append((self.current_province, paragraph))
            self.capture_p = False
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.capture_h3 or self.capture_p:
            self.buffer.append(data)

    @staticmethod
    def _clean(value: str) -> str:
        text = html.unescape(value).replace("\xa0", " ")
        text = text.replace("\r", "\n")
        text = re.sub(r"\n+", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


class InstaleapLocationScraper:
    def __init__(self, *, config: InstaleapLocationChainConfig) -> None:
        self.config = config
        self.session = self._build_session()
        self._stores_nearby_cache: dict[tuple[float, float], list[dict[str, Any]]] = {}
        self._request_counter = 0

    def _build_session(self) -> BrowserSession:
        domain = self.config.graphql_v2_endpoint.removeprefix("https://").removeprefix("http://").split("/")[0]
        set_rate_limiter(domain)
        urllib3.disable_warnings()
        return create_browser_session(
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": "https://www.megasuper.com/",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
                ),
            }
        )

    def _sleep_if_needed(self) -> None:
        return

    def fetch_source_html(self) -> str:
        response = request_with_retry(
            self.session,
            "GET",
            SOURCE_URL,
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        response.raise_for_status()
        return response.content.decode("utf-8-sig", errors="replace")

    def fetch_source_kml(self) -> str:
        response = request_with_retry(
            self.session,
            "GET",
            SOURCE_MAP_KML_URL,
            timeout=REQUEST_TIMEOUT,
            verify=False,
        )
        self._request_counter += 1
        response.raise_for_status()
        return response.text

    def parse_entries(self, source_html: str) -> list[tuple[str | None, str]]:
        parser = SucursalesHtmlParser()
        parser.feed(source_html)
        return parser.entries

    def parse_kml_placemarks(self, source_kml: str) -> list[KmlPlacemark]:
        root = ET.fromstring(source_kml)
        placemarks: list[KmlPlacemark] = []
        for node in root.findall(".//kml:Placemark", KML_NS):
            name = normalize_string(node.findtext("kml:name", default="", namespaces=KML_NS))
            coordinates_text = normalize_string(
                node.findtext(".//kml:coordinates", default="", namespaces=KML_NS)
            )
            if not name or not coordinates_text:
                continue
            parts = [part.strip() for part in coordinates_text.split(",")]
            if len(parts) < 2:
                continue
            try:
                longitude = float(parts[0])
                latitude = float(parts[1])
            except ValueError:
                continue
            placemarks.append(
                KmlPlacemark(
                    name=name,
                    latitude=latitude,
                    longitude=longitude,
                    description=normalize_string(
                        node.findtext("kml:description", default="", namespaces=KML_NS)
                    ),
                )
            )
        return placemarks

    def parse_entry(self, province: str | None, raw_entry: str) -> dict[str, Any]:
        parts = [part.strip(" -") for part in raw_entry.split("\n") if part.strip()]
        location_name = parts[0]
        remainder = " ".join(parts[1:]).strip()
        phone = None
        address_text = remainder or None

        phone_match = re.search(r"(?i)\bTel:\s*([0-9()+ -]+)$", remainder)
        if phone_match:
            phone = normalize_string(phone_match.group(1))
            address_text = normalize_string(remainder[: phone_match.start()].strip(" .-"))

        location_code = slugify(location_name)
        return {
            "chain_id": self.config.chain_id,
            "location_code": location_code,
            "source_engine": "instaleap",
            "source_location_ref": None,
            "source_internal_id": None,
            "location_name": location_name,
            "location_type": "physical_store",
            "sales_channel": None,
            "region_id": None,
            "address_text": address_text,
            "province": normalize_string(province),
            "canton": None,
            "district": None,
            "postal_code": None,
            "latitude": None,
            "longitude": None,
            "phone": phone,
            "is_default": False,
            "source_origin": "chain_site_page",
            "source_payload": {
                "source_url": SOURCE_URL,
                "raw_entry": raw_entry,
            },
        }

    def match_kml_placemark(
        self,
        *,
        location_name: str,
        placemarks: list[KmlPlacemark],
    ) -> tuple[KmlPlacemark | None, float]:
        if not placemarks:
            return None, 0.0
        scored = sorted(
            ((similarity_score(location_name, placemark.name), placemark) for placemark in placemarks),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best_placemark = scored[0]
        return best_placemark, best_score

    def fetch_stores_nearby(self, *, latitude: float, longitude: float) -> list[dict[str, Any]]:
        cache_key = (round(latitude, 6), round(longitude, 6))
        cached = self._stores_nearby_cache.get(cache_key)
        if cached is not None:
            return cached

        payload = {
            "operationName": "GetStoresNearbyByCoords",
            "query": STORES_NEARBY_QUERY,
            "variables": {
                "clientId": self.config.client_id,
                "operationalModel": "DELIVERY",
                "coordinates": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
            },
        }

        self._sleep_if_needed()
        response = request_with_retry(
            self.session,
            "GET",
            self.config.graphql_v2_endpoint,
            timeout=GRAPHQL_TIMEOUT,
            verify=False,
            params={
                "operationName": payload["operationName"],
                "query": payload["query"],
                "variables": json.dumps(payload["variables"], separators=(",", ":")),
            },
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.megasuper.com",
                "Referer": "https://www.megasuper.com/",
            },
        )
        self._request_counter += 1
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise RuntimeError(
                "Instaleap v2 storesNearby devolvió errores: "
                + json.dumps(data["errors"], ensure_ascii=False)[:1200]
            )
        stores = (data.get("data") or {}).get("getStoresNearbyByCoords") or []
        if not isinstance(stores, list):
            raise RuntimeError("Respuesta inválida de Instaleap v2: getStoresNearbyByCoords no es lista.")
        self._stores_nearby_cache[cache_key] = stores
        return stores

    def score_store_candidate(self, row: dict[str, Any], store: dict[str, Any]) -> float:
        score = similarity_score(row["location_name"], store.get("name"))
        province = normalize_name_for_match(row.get("province"))
        state = normalize_name_for_match(store.get("state"))
        if province and state and province == state:
            score += 0.03
        cities = " ".join(normalize_string(city.get("name")) or "" for city in store.get("cities") or [])
        location_name_normalized = normalize_name_for_match(row["location_name"])
        cities_normalized = normalize_name_for_match(cities)
        if cities_normalized and cities_normalized in location_name_normalized:
            score += 0.08
        address_text = normalize_name_for_match(row.get("address_text"))
        store_address = normalize_name_for_match(store.get("address"))
        if address_text and store_address:
            overlap = set(address_text.split()) & set(store_address.split())
            if overlap:
                score += min(len(overlap) * 0.02, 0.08)
        return score

    def enrich_row_with_instaleap_store(
        self,
        *,
        row: dict[str, Any],
        placemarks: list[KmlPlacemark],
    ) -> None:
        placemark, placemark_score = self.match_kml_placemark(
            location_name=row["location_name"],
            placemarks=placemarks,
        )
        if placemark is None:
            row["source_payload"]["kml_match_status"] = "missing"
            return

        row["latitude"] = placemark.latitude
        row["longitude"] = placemark.longitude
        row["source_payload"]["kml_match_status"] = "matched"
        row["source_payload"]["kml_name"] = placemark.name
        row["source_payload"]["kml_match_score"] = round(placemark_score, 4)
        row["source_payload"]["kml_source_url"] = SOURCE_MAP_KML_URL

        stores = self.fetch_stores_nearby(latitude=placemark.latitude, longitude=placemark.longitude)
        if not stores:
            row["source_payload"]["nearby_store_match_status"] = "no_candidates"
            return

        scored_candidates = sorted(
            ((self.score_store_candidate(row, store), store) for store in stores),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best_store = scored_candidates[0]
        row["source_payload"]["nearby_store_match_score"] = round(best_score, 4)
        row["source_payload"]["nearby_store_top_candidates"] = [
            {
                "name": normalize_string(store.get("name")),
                "code": normalize_string(store.get("code")),
                "id": normalize_string(store.get("id")),
                "score": round(score, 4),
            }
            for score, store in scored_candidates[:3]
        ]

        if best_score < 0.70:
            row["source_payload"]["nearby_store_match_status"] = "low_confidence"
            return

        row["source_location_ref"] = normalize_string(best_store.get("code"))
        row["source_internal_id"] = normalize_string(best_store.get("id"))
        row["source_payload"]["nearby_store_match_status"] = "matched"
        row["source_payload"]["resolved_store_name"] = normalize_string(best_store.get("name"))
        row["source_payload"]["resolved_store_address"] = normalize_string(best_store.get("address"))

    def discover_locations(self) -> list[dict[str, Any]]:
        source_html = self.fetch_source_html()
        source_kml = self.fetch_source_kml()
        parsed_entries = self.parse_entries(source_html)
        placemarks = self.parse_kml_placemarks(source_kml)
        deduped: dict[str, dict[str, Any]] = {}

        default_location_code = slugify("Megasuper La Paz")

        for province, raw_entry in parsed_entries:
            row = self.parse_entry(province, raw_entry)
            self.enrich_row_with_instaleap_store(row=row, placemarks=placemarks)
            location_code = row["location_code"]
            if location_code in deduped:
                continue
            if location_code == default_location_code:
                row["is_default"] = True
                row["source_location_ref"] = (
                    row["source_location_ref"] or self.config.default_store_reference
                )
                row["source_internal_id"] = (
                    row["source_internal_id"] or self.config.default_store_internal_id
                )
                row["source_payload"]["default_chain_store_reference"] = (
                    self.config.default_store_reference
                )
                row["source_payload"]["default_chain_store_internal_id"] = (
                    self.config.default_store_internal_id
                )
            deduped[location_code] = row

        locations = sorted(deduped.values(), key=lambda item: item["location_name"])
        resolved_count = sum(1 for row in locations if row.get("source_location_ref"))
        print(
            f"[{self.config.chain_id}] sucursales descubiertas: {len(locations)} | "
            f"resueltas con contexto tecnico: {resolved_count}",
            flush=True,
        )
        return locations


def discover_locations(chain_id: str) -> list[dict[str, Any]]:
    scraper = InstaleapLocationScraper(config=load_chain_runtime_config(chain_id))
    return scraper.discover_locations()
