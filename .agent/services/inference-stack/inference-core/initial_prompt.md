# Service: Inference Core

Core engine for AI model execution and inference within the DataSyncSA ecosystem.

## Context
- **Path:** `services/inference-stack/inference-core`
- **Goal:** Providing high-performance inference endpoints for internal services.

## Operational Rules
1. Refer to `architecture.md` for GPU/CPU resource allocation and model loading logic.
2. Check `specs.md` for API endpoint definitions and supported models.
3. Ensure the `inference-core` can communicate with the `semantic-adapter`.
