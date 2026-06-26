from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrightDataConfig:
    customer_id: str
    zone: str
    password: str
    host: str = "brd.superproxy.io"
    port: int = 33335
    country: str | None = None
    session: str | None = None

    @property
    def username(self) -> str:
        parts = [f"brd-customer-{self.customer_id}-zone-{self.zone}"]
        if self.country:
            parts.append(f"country-{self.country.lower()}")
        if self.session:
            parts.append(f"session-{self.session}")
        return "-".join(parts)

    @property
    def proxy_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def as_proxies_dict(self) -> dict[str, str]:
        auth = f"{self.username}:{self.password}"
        proxy = f"http://{auth}@{self.host}:{self.port}"
        return {"http": proxy, "https": proxy}

    def as_curl_cffi_kwargs(self) -> dict[str, Any]:
        return {"proxies": self.as_proxies_dict()}


def config_from_env(
    *,
    country: str | None = None,
    session: str | None = None,
) -> BrightDataConfig:
    return BrightDataConfig(
        customer_id=os.environ["BRIGHTDATA_CUSTOMER_ID"],
        zone=os.environ["BRIGHTDATA_ZONE"],
        password=os.environ["BRIGHTDATA_ZONE_PASSWORD"],
        country=country or os.environ.get("BRIGHTDATA_COUNTRY"),
        session=session,
    )
