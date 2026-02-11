# Service: ETL Processor

This service handles the data extraction, transformation, and loading logic for DataSyncSA.

## Context
- **Path:** `services/etl-processor`
- **Dependencies:** Database stack (PostgreSQL), R2 Storage.
- **Goal:** Efficient processing of incoming data streams into the unified schema.

## Operational Rules
1. Refer to `architecture.md` for the data pipeline flow.
2. Check `specs.md` for specific ETL job definitions and cron schedules.
3. Ensure Rclone mounts are active before starting high-volume transfers.
