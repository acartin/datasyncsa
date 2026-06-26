#!/usr/bin/env python3
"""Unit tests for analytic campaign command helpers."""

from __future__ import annotations

import unittest

from commands.extract_campaign_analytic_to_stage import (
    FAILED_RECORD_ERROR_SAMPLE_LIMIT,
    FAILED_RECORD_ERROR_TEXT_LIMIT,
    build_failed_analytic_metadata,
)


class FailedAnalyticMetadataTests(unittest.TestCase):
    def test_preserves_scraper_error_summary_for_zero_record_failures(self) -> None:
        long_error = "x" * (FAILED_RECORD_ERROR_TEXT_LIMIT + 50)
        scraper_metadata = {
            "engine": "vtex",
            "chain_id": "masxmenos_cr",
            "catalog_id": "mxm",
            "pricing_scope": "physical_store_online",
            "started_at": "2026-06-15T16:53:38+00:00",
            "finished_at": "2026-06-15T16:55:45+00:00",
            "elapsed_seconds": 127.12,
            "catalog_records": 0,
            "unique_products": 0,
            "campaign_record_total_requested": 32,
            "campaign_record_total_succeeded": 0,
            "campaign_record_total_failed": 32,
            "http_request_count": 64,
            "http_response_body_bytes": 12345,
            "campaign_record_errors": [
                {
                    "listing_key": index,
                    "product_key": 1000 + index,
                    "product_name": f"Product {index}",
                    "error": long_error,
                }
                for index in range(FAILED_RECORD_ERROR_SAMPLE_LIMIT + 3)
            ],
        }

        metadata = build_failed_analytic_metadata(
            campaign_id=1,
            location_key=8,
            location_name="MxM-LIMON",
            requested_targets=32,
            source_domain="www.masxmenos.cr",
            scraper_metadata=scraper_metadata,
            error_message="No se obtuvieron registros exitosos para esta location.",
        )

        self.assertEqual(metadata["campaign_id"], 1)
        self.assertEqual(metadata["source_domain"], "www.masxmenos.cr")
        self.assertEqual(metadata["campaign_record_total_failed"], 32)
        self.assertEqual(metadata["http_request_count"], 64)
        self.assertEqual(
            metadata["campaign_record_error_total"],
            FAILED_RECORD_ERROR_SAMPLE_LIMIT + 3,
        )
        self.assertEqual(
            len(metadata["campaign_record_error_sample"]),
            FAILED_RECORD_ERROR_SAMPLE_LIMIT,
        )
        self.assertTrue(metadata["campaign_record_errors_truncated"])
        self.assertIn("[truncated]", metadata["campaign_record_error_sample"][0]["error"])

    def test_builds_minimal_failure_metadata_without_scraper_metadata(self) -> None:
        metadata = build_failed_analytic_metadata(
            campaign_id=1,
            location_key=7,
            location_name="MxM-SABANA",
            requested_targets=32,
            source_domain="www.masxmenos.cr",
            error_message="boom",
        )

        self.assertEqual(
            metadata,
            {
                "campaign_id": 1,
                "location_key": 7,
                "location_name": "MxM-SABANA",
                "requested_targets": 32,
                "source_domain": "www.masxmenos.cr",
                "failure_reason": "boom",
            },
        )


if __name__ == "__main__":
    unittest.main()
