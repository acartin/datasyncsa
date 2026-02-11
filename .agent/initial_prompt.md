# Agent Router Prompt

You are working in a consolidated infrastructure for **DataSyncSA**. This workspace contains multiple services managed via Docker Compose.

## Strategy for Context Discovery

Before performing any action, you MUST identify which service you are interacting with. Follow these steps:

1. **Identify Service:** Determine the target service directory in `services/`.
2. **Load Global Rules:** Read `.agent/global_rules.md` for infrastructure standards (Nginx, Docker, Volumes).
3. **Load Service Context:** Locate and read the service-specific `initial_prompt.md` in:
   `.agent/services/[category]/[service-name]/initial_prompt.md`
4. **Read Technical Specs:** Consult `architecture.md` and `specs.md` in the same directory for deep technical details.

## Services Map

- **ETL:** `services/etl-processor`
- **Inference Stack:**
  - `services/inference-stack/inference-core`
  - `services/inference-stack/semantic-adapter`
- **Web Stack:**
  - `services/web/admin-console`
  - `services/web/datasyncsa`
  - `services/web/realtor-chat`

Always operate with the specific context of the service to avoid cross-contamination of architectural patterns.
