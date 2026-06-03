# Retail Signal Engine

Batch service for Market Watch retail intelligence signals.

This service does not scrape, serve HTTP, or render dashboards. It reads prepared
Market Watch facts/views, creates neutral market events, creates perspective
client signals, optionally asks an LLM to synthesize executive narrative, and
persists the result in Postgres.

## Signal Types

### Executive signals (mkt_client_signal)

| Type | Effect | What it detects |
|---|---|---|
| `brand_over_market` | negative | Brand price index >105% of market |
| `brand_under_market` | positive | Brand price index <95% of market |
| `sku_price_gap` | negative | SKU gap >10% vs best market price |
| `driver_sku_detected` | negative | 3 SKUs concentrate >60% of total brand gap |
| `promo_price_break` | positive | Discount >15%, gap vs market >20%, >50% stores on promo |

### Transition events (mkt_market_event only)

Generated day-over-day from `mw_core_sku_store_observation`. These are stored
as neutral events and are used by the Intraday Radar grid:

| Event type | Area | Trigger |
|---|---|---|
| `promo_started` | promotion | Promo detected today, none yesterday |
| `promo_ended` | promotion | Promo detected yesterday, none today |
| `regular_price_increase` | price | Reference price went up |
| `regular_price_decrease` | price | Reference price went down |
| `promo_price_increase` | price | Promo price went up |
| `promo_price_decrease` | price | Promo price went down |

Transition events are computed by `generate_day_over_day_transition_events()`
inside the same batch. They are persisted directly to `mkt_market_event` and
do not generate executive signals by default.

Event presentation is configured centrally in `public.mkt_dim_market_event_type`.
Add or change labels, metric labels, semantic icon names, and renderer tokens
there instead of hardcoding event-specific presentation in API or frontend code.

## Tables

- `public.mkt_market_event`: neutral reusable market events (executive + transition).
- `public.mkt_dim_market_event_type`: central event semantics and presentation configuration.
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

## Usage

Apply schema:

```bash
python3 services/retail-signal-engine/commands/generate_daily_signals.py --init-schema --dry-run
```

Generate latest signals for a campaign (includes transition events):

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

Skip day-over-day transition events:

```bash
python3 services/retail-signal-engine/commands/generate_daily_signals.py \
  --business-date 2026-05-21 \
  --campaign-id 1 \
  --no-include-transitions
```

From Dagster (launchpad):

```bash
# Job: daily_signal_generation_job
# Op: generate_retail_signals
# Config:
#   campaign_id: 1
#   business_date: "2026-05-27"
#   skip_llm: true
```

Required environment:

- `DB_USER`
- `DB_NAME`
- `DATABASE_URL` or Docker Compose Postgres access
- `GOOGLE_API_KEY` when LLM synthesis is enabled
- `LLM_DEFAULT_MODEL`, default `gemini-2.5-flash-lite`
