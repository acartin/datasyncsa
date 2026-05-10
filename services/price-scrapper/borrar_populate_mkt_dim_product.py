#!/usr/bin/env python3
"""Build and load mkt_dim_product from the four current catalog snapshots.

This is intentionally throwaway code, hence the `borrar_` prefix.

Behavior:
- reads the four `output/chains/*/catalog.json` files
- auto-loads only safe GTIN groups into `public.mkt_dim_product`
- writes problematic groups to a JSON file for manual review

Problematic groups currently mean:
- invalid or non-standard GTINs
- valid GTINs that collide inside the same chain with multiple listings
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = Path(__file__).resolve().parent
CATALOG_ROOT = SERVICE_ROOT / "output" / "chains"
REVIEW_DIR = SERVICE_ROOT / "output" / "manual_review"
REVIEW_JSON_PATH = REVIEW_DIR / "borrar_mkt_dim_product_manual_review.json"
ENV_PATH = REPO_ROOT / ".env"

CHAIN_PRIORITY = {
    "walmart_cr": 0,
    "maxi_pali_cr": 1,
    "masxmenos_cr": 2,
    "megasuper_cr": 3,
}

VALID_GTIN_LENGTHS = {8, 12, 13, 14}
UNIT_CANONICALIZATION = {
    "g": ("g", Decimal("1")),
    "gr": ("g", Decimal("1")),
    "kg": ("g", Decimal("1000")),
    "ml": ("ml", Decimal("1")),
    "l": ("ml", Decimal("1000")),
    "lt": ("ml", Decimal("1000")),
    "lts": ("ml", Decimal("1000")),
    "un": ("un", Decimal("1")),
    "u": ("un", Decimal("1")),
    "ud": ("un", Decimal("1")),
    "uds": ("un", Decimal("1")),
}


@dataclass
class CatalogRow:
    chain_id: str
    gtin_raw: str | None
    gtin_norm: str | None
    gtin_type: str | None
    gtin_is_valid: bool
    sku: str | None
    product_id: str | None
    brand_name: str | None
    brand_norm: str
    product_name: str
    name_norm: str
    quantity: str | None
    unit: str | None
    measurement_unit: str | None


def parse_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def digits_only(value: object) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value).strip())
    return digits or None


def gtin_type(code: str | None) -> str | None:
    if not code:
        return None
    length = len(code)
    if length == 8:
        return "GTIN8"
    if length == 12:
        return "GTIN12"
    if length == 13:
        return "GTIN13"
    if length == 14:
        return "GTIN14"
    return "NON_STANDARD"


def is_valid_gtin(code: str | None) -> bool:
    if not code or len(code) not in VALID_GTIN_LENGTHS or not code.isdigit():
        return False
    body = code[:-1]
    check_digit = int(code[-1])
    total = 0
    for idx, char in enumerate(reversed(body), start=1):
        total += int(char) * (3 if idx % 2 == 1 else 1)
    expected = (10 - (total % 10)) % 10
    return check_digit == expected


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def flatten_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def safe_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def normalize_measure(quantity: object, unit: str | None) -> tuple[Decimal, str] | None:
    q = safe_decimal(quantity)
    if q is None or not unit:
        return None
    normalized_unit = unit.strip().lower()
    if normalized_unit not in UNIT_CANONICALIZATION:
        return None
    canonical_unit, multiplier = UNIT_CANONICALIZATION[normalized_unit]
    return (q * multiplier, canonical_unit)


def preferred_row(rows: list[CatalogRow]) -> CatalogRow:
    name_freq = Counter(row.name_norm for row in rows)
    brand_freq = Counter(row.brand_norm for row in rows)

    def sort_key(row: CatalogRow) -> tuple[int, int, int, int, int]:
        is_mixed_case = 0 if row.product_name == row.product_name.upper() else 1
        return (
            -name_freq[row.name_norm],
            -brand_freq[row.brand_norm],
            CHAIN_PRIORITY.get(row.chain_id, 99),
            -is_mixed_case,
            -len(row.product_name),
        )

    return sorted(rows, key=sort_key)[0]


def consensus_measure(rows: list[CatalogRow]) -> tuple[str | None, str | None]:
    normalized = [normalize_measure(row.quantity, row.unit) for row in rows]
    non_null = [entry for entry in normalized if entry is not None]
    if not non_null:
        return (None, None)
    unique = set(non_null)
    if len(unique) != 1:
        return (None, None)
    quantity, unit = next(iter(unique))
    quantity_text = format(quantity, "f")
    if "." in quantity_text:
        quantity_text = quantity_text.rstrip("0").rstrip(".")
    return (quantity_text, unit)


def load_catalog_rows() -> list[CatalogRow]:
    rows: list[CatalogRow] = []
    for catalog_path in sorted(CATALOG_ROOT.glob("*/catalog.json")):
        chain_id = catalog_path.parent.name
        items = json.loads(catalog_path.read_text())
        for item in items:
            identity = item.get("identity") or {}
            content = item.get("content") or {}
            measurement = item.get("measurement") or {}
            code = digits_only(identity.get("ean"))
            name = str(content.get("name") or "").strip()
            rows.append(
                CatalogRow(
                    chain_id=chain_id,
                    gtin_raw=str(identity.get("ean")).strip() if identity.get("ean") is not None else None,
                    gtin_norm=code,
                    gtin_type=gtin_type(code),
                    gtin_is_valid=is_valid_gtin(code),
                    sku=str(identity.get("sku")).strip() if identity.get("sku") is not None else None,
                    product_id=str(identity.get("product_id")).strip()
                    if identity.get("product_id") is not None
                    else None,
                    brand_name=str(identity.get("brand")).strip() if identity.get("brand") is not None else None,
                    brand_norm=normalize_text(identity.get("brand")),
                    product_name=name,
                    name_norm=normalize_text(name),
                    quantity=str(measurement.get("quantity")).strip()
                    if measurement.get("quantity") is not None
                    else None,
                    unit=str(measurement.get("unit")).strip() if measurement.get("unit") is not None else None,
                    measurement_unit=str(measurement.get("measurement_unit")).strip()
                    if measurement.get("measurement_unit") is not None
                    else None,
                )
            )
    return rows


def build_manual_review_payload(
    invalid_groups: list[tuple[str | None, list[CatalogRow]]],
    same_chain_collision_groups: list[tuple[str, list[CatalogRow]]],
    inserted_count: int,
    benign_variant_count: int,
    total_rows: int,
    total_gtin_groups: int,
) -> dict[str, object]:
    def serialize_group(reason: str, gtin_norm_value: str | None, group: list[CatalogRow]) -> dict[str, object]:
        return {
            "reason": reason,
            "gtin_norm": gtin_norm_value,
            "gtin_type": gtin_type(gtin_norm_value),
            "group_size": len(group),
            "chains": sorted({row.chain_id for row in group}),
            "entries": [
                {
                    "chain_id": row.chain_id,
                    "gtin_raw": row.gtin_raw,
                    "gtin_norm": row.gtin_norm,
                    "sku": row.sku,
                    "product_id": row.product_id,
                    "brand_name": row.brand_name,
                    "product_name": row.product_name,
                    "quantity": row.quantity,
                    "unit": row.unit,
                    "measurement_unit": row.measurement_unit,
                }
                for row in group
            ],
        }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_source_rows": total_rows,
            "total_gtin_groups": total_gtin_groups,
            "inserted_products": inserted_count,
            "manual_review_group_count": len(invalid_groups) + len(same_chain_collision_groups),
            "invalid_or_nonstandard_group_count": len(invalid_groups),
            "same_chain_collision_group_count": len(same_chain_collision_groups),
            "benign_cross_chain_variant_count": benign_variant_count,
        },
        "invalid_or_nonstandard_gtins": [
            serialize_group("invalid_or_nonstandard_gtin", gtin_norm_value, group)
            for gtin_norm_value, group in invalid_groups
        ],
        "valid_gtin_same_chain_collisions": [
            serialize_group("same_chain_duplicate_valid_gtin", gtin_norm_value, group)
            for gtin_norm_value, group in same_chain_collision_groups
        ],
    }


def group_rows(rows: Iterable[CatalogRow]) -> dict[str | None, list[CatalogRow]]:
    grouped: dict[str | None, list[CatalogRow]] = defaultdict(list)
    for row in rows:
        grouped[row.gtin_norm].append(row)
    return grouped


def load_into_db(rows_to_load: list[dict[str, object]], env: dict[str, str]) -> None:
    if not rows_to_load:
        return

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=[
            "gtin_raw",
            "gtin_norm",
            "gtin_type",
            "gtin_is_valid",
            "brand_name",
            "product_name",
            "normalized_name",
            "content_quantity",
            "content_unit",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows_to_load:
        writer.writerow(
            {
                **row,
                "brand_name": flatten_text(row["brand_name"]),
                "product_name": flatten_text(row["product_name"]),
                "normalized_name": flatten_text(row["normalized_name"]),
                "content_unit": flatten_text(row["content_unit"]),
            }
        )

    sql = f"""
begin;
create temp table tmp_borrar_mkt_dim_product_load (
  gtin_raw text,
  gtin_norm text,
  gtin_type text,
  gtin_is_valid boolean,
  brand_name text,
  product_name text,
  normalized_name text,
  content_quantity numeric(14,4),
  content_unit varchar(30)
);
copy tmp_borrar_mkt_dim_product_load (
  gtin_raw,
  gtin_norm,
  gtin_type,
  gtin_is_valid,
  brand_name,
  product_name,
  normalized_name,
  content_quantity,
  content_unit
) from stdin with (format csv, header true);
{csv_buffer.getvalue()}\\.
update public.mkt_dim_product as p
set
  gtin_raw = t.gtin_raw,
  brand_name = t.brand_name,
  product_name = t.product_name,
  normalized_name = t.normalized_name,
  content_quantity = t.content_quantity,
  content_unit = t.content_unit,
  is_active = true,
  updated_at = now()
from tmp_borrar_mkt_dim_product_load as t
where p.gtin_is_valid = true
  and p.gtin_norm = t.gtin_norm;

insert into public.mkt_dim_product (
  gtin_raw,
  gtin_norm,
  gtin_type,
  gtin_is_valid,
  brand_name,
  product_name,
  normalized_name,
  content_quantity,
  content_unit,
  is_active
)
select
  t.gtin_raw,
  t.gtin_norm,
  t.gtin_type,
  t.gtin_is_valid,
  t.brand_name,
  t.product_name,
  t.normalized_name,
  t.content_quantity,
  t.content_unit,
  true
from tmp_borrar_mkt_dim_product_load as t
where not exists (
  select 1
  from public.mkt_dim_product as p
  where p.gtin_is_valid = true
    and p.gtin_norm = t.gtin_norm
);
commit;
"""

    command = [
        "docker",
        "compose",
        "--env-file",
        str(ENV_PATH),
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        env["DB_USER"],
        "-d",
        env["DB_NAME"],
        "-v",
        "ON_ERROR_STOP=1",
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        input=sql,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def fetch_db_count(env: dict[str, str]) -> int:
    command = [
        "docker",
        "compose",
        "--env-file",
        str(ENV_PATH),
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        env["DB_USER"],
        "-d",
        env["DB_NAME"],
        "-Atc",
        "select count(*) from public.mkt_dim_product;",
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return int(result.stdout.strip())


def main() -> int:
    if not ENV_PATH.exists():
        print(f"Missing env file: {ENV_PATH}", file=sys.stderr)
        return 1

    env = parse_env(ENV_PATH)
    for required_key in ("DB_USER", "DB_NAME"):
        if not env.get(required_key):
            print(f"Missing required env var in {ENV_PATH}: {required_key}", file=sys.stderr)
            return 1

    rows = load_catalog_rows()
    grouped = group_rows(rows)

    invalid_groups: list[tuple[str | None, list[CatalogRow]]] = []
    same_chain_collision_groups: list[tuple[str, list[CatalogRow]]] = []
    safe_groups: list[tuple[str, list[CatalogRow]]] = []
    benign_variant_count = 0

    for gtin_norm_value, group in grouped.items():
        if not gtin_norm_value or not group[0].gtin_is_valid:
            invalid_groups.append((gtin_norm_value, group))
            continue

        per_chain = Counter(row.chain_id for row in group)
        if any(count > 1 for count in per_chain.values()):
            same_chain_collision_groups.append((gtin_norm_value, group))
            continue

        name_variants = {row.name_norm for row in group}
        brand_variants = {row.brand_norm for row in group}
        if len(name_variants) > 1 or len(brand_variants) > 1:
            benign_variant_count += 1

        safe_groups.append((gtin_norm_value, group))

    rows_to_load: list[dict[str, object]] = []
    for gtin_norm_value, group in safe_groups:
        representative = preferred_row(group)
        content_quantity, content_unit = consensus_measure(group)
        rows_to_load.append(
            {
                "gtin_raw": representative.gtin_raw,
                "gtin_norm": gtin_norm_value,
                "gtin_type": representative.gtin_type,
                "gtin_is_valid": "true",
                "brand_name": representative.brand_name,
                "product_name": representative.product_name,
                "normalized_name": representative.name_norm.lower(),
                "content_quantity": content_quantity,
                "content_unit": content_unit,
            }
        )

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    review_payload = build_manual_review_payload(
        invalid_groups=invalid_groups,
        same_chain_collision_groups=same_chain_collision_groups,
        inserted_count=len(rows_to_load),
        benign_variant_count=benign_variant_count,
        total_rows=len(rows),
        total_gtin_groups=len(grouped),
    )
    REVIEW_JSON_PATH.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2))

    load_into_db(rows_to_load, env)
    db_count = fetch_db_count(env)

    print("mkt_dim_product load complete")
    print(f"source_rows={len(rows)}")
    print(f"unique_gtin_groups={len(grouped)}")
    print(f"inserted_or_updated={len(rows_to_load)}")
    print(f"manual_review_groups={len(invalid_groups) + len(same_chain_collision_groups)}")
    print(f"review_json={REVIEW_JSON_PATH}")
    print(f"db_row_count={db_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
