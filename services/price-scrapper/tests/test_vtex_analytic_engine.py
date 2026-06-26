#!/usr/bin/env python3
"""Unit tests for the VTEX analytic engine."""

from __future__ import annotations

import unittest

from engines.vtex_analytic_engine import (
    VtexAnalyticScraper,
    VtexAnalyticTarget,
)


def build_target() -> VtexAnalyticTarget:
    return VtexAnalyticTarget(
        product_key=1,
        product_role="competitor",
        gtin_raw=None,
        brand_name="Brand",
        product_name="Promo product",
        content_quantity="420",
        content_unit="g",
        listing_key=10,
        source_product_id="401",
        source_sku="84773",
        seller_id="1",
        seller_name="Seller",
        listing_name="Promo product listing",
        product_url="https://example.test/promo/p",
        image_url=None,
        root_category_slug="atun",
        root_category_name="Atun",
    )


class FakeVtexAnalyticScraper(VtexAnalyticScraper):
    def __init__(self, product_payload: dict) -> None:
        self.product_payload = product_payload
        self.checkout_called = False

    def fetch_catalog_product(self, target: VtexAnalyticTarget) -> dict:
        return self.product_payload

    def fetch_checkout_simulation(self, target: VtexAnalyticTarget) -> dict:
        self.checkout_called = True
        raise AssertionError("checkout simulation must not run in analytic pricing")


class VtexAnalyticEngineTests(unittest.TestCase):
    def test_derive_observed_payload_uses_catalog_offer_promo_without_checkout_post(self) -> None:
        scraper = FakeVtexAnalyticScraper(
            {
                "items": [
                    {
                        "itemId": "84773",
                        "sellers": [
                            {
                                "sellerId": "1",
                                "sellerName": "Seller",
                                "commertialOffer": {
                                    "Price": 3000.0,
                                    "ListPrice": 3610.0,
                                    "PriceWithoutDiscount": 3000.0,
                                    "spotPrice": None,
                                    "AvailableQuantity": 10,
                                    "DiscountHighLight": [],
                                    "teasers": [],
                                },
                            }
                        ],
                    }
                ]
            }
        )

        observed = scraper.derive_observed_payload(build_target())

        self.assertFalse(scraper.checkout_called)
        self.assertEqual(observed["price"], 3000.0)
        self.assertEqual(observed["list_price"], 3610.0)
        self.assertTrue(observed["has_discount"])
        self.assertEqual(observed["pricing_signal_kind"], "catalog_system_products_search")


if __name__ == "__main__":
    unittest.main()
