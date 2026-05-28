# Retail Signal Engine

Batch service for Market Watch retail intelligence signals.

This service does not scrape, serve HTTP, or render dashboards. It reads prepared
Market Watch facts/views, creates neutral market events, creates perspective
client signals, optionally asks an LLM to synthesize executive narrative, and
persists the result in Postgres.

## V1 Scope

Initial signal types:

- `brand_over_market`
- `brand_under_market`
- `sku_price_gap`
- `driver_sku_detected`

The LLM is only used after metrics, scoring, and evidence are already built by
deterministic code.

## Tables

- `public.mkt_market_event`: neutral reusable market events.
- `public.mkt_client_signal`: perspective-specific signal packaging, lifecycle
  state, and notification readiness.
- `public.mkt_signal_delivery`: future audit log for email/PDF/other delivery
  attempts.

## Signal Lifecycle

Each client signal has:

- `fingerprint_key`: stable identity for the same commercial signal across days.
- `lifecycle_status`: `new`, `active`, `worsened`, or `improved`.
- `previous_client_signal_id`: previous signal instance used for comparison.
- `repeat_count`: number of consecutive detected instances known by the engine.
- `delta_metrics_json`: previous/current strength comparison.
- `navigation_json`: tool-agnostic contract for opening the right dashboard,
  tab, filters, and evidence dataset.
- `notification_status` / `notification_reason`: placeholders for the later
  delivery scheduler.

This keeps the executive feed from blindly repeating yesterday's finding. A
future delivery process can choose to notify only `new` and `worsened` signals,
or include `improved` signals in a separate section.

Apply schema:

```bash
python3 services/retail-signal-engine/commands/generate_daily_signals.py --init-schema --dry-run
```

Generate latest signals for a campaign:

```bash
python3 services/retail-signal-engine/commands/generate_daily_signals.py \
  --campaign-id 1 \
  --max-signals 12
```

Generate a specific business date:

```bash
python3 services/retail-signal-engine/commands/generate_daily_signals.py \
  --business-date 2026-05-21 \
  --campaign-id 1
```

Skip LLM synthesis and use deterministic templates:

```bash
python3 services/retail-signal-engine/commands/generate_daily_signals.py \
  --business-date 2026-05-21 \
  --campaign-id 1 \
  --skip-llm
```

Required environment:

- `DB_USER`
- `DB_NAME`
- `DATABASE_URL` or Docker Compose Postgres access
- `GOOGLE_API_KEY` when LLM synthesis is enabled
- `LLM_DEFAULT_MODEL`, default `gemini-2.5-flash-lite`
