# mkt_dim_market_event_type

Central semantic and presentation configuration dimension for Market Watch events.

## Purpose

Prevents `event_type` from being hardcoded across SQL views, API code, or frontend components. Each configurable event is defined in one row, and the API exposes that configuration to the portal.

## Grain

One row per `event_type`.

## Main Columns

| Column | Use |
|---|---|
| `event_type` | Stable key used by ETL, events, and API. |
| `event_area` | Semantic family: `price`, `promotion`, `competitive`, etc. |
| `display_label` | Operational title for event headers, for example `PROMOTION STARTED`. |
| `short_label` | Short label for tables, chips, or chart annotations. |
| `metric_previous_label` | Previous metric label for event headers. |
| `metric_current_label` | Current metric label for event headers. |
| `metric_change_label` | Change metric label for event headers. |
| `value_format` | Semantic value format: `currency`, `percent`, `number`, etc. |
| `change_format` | Semantic change format: `percent`, `points`, `currency`, etc. |
| `direction_semantics` | Direction meaning: `positive_good`, `positive_bad`, `negative_good`, `negative_bad`, `neutral`. |
| `header_variant` | Visual composition variant: `price`, `promotion`, `competitive`, `generic`. |
| `icon_name` | Semantic icon name translated by the frontend. |
| `accent_token` | Semantic token: `success`, `danger`, `warning`, `info`, `neutral`. Do not store colors or CSS classes. |
| `appears_in_intraday_radar` | Controls whether the event appears in Price and Promotions Radar. |
| `creates_client_signal` | Indicates whether the event is packaged as an executive signal. |
| `presentation_config` | Optional JSON with semantic renderer hints. |

## Rules

- Do not store Tailwind classes, hex colors, or component-specific copy.
- Add new event types here before exposing them in API or UI.
- API queries should join by `event_type` and return the presentation configuration.
- Frontend components should render a generic fallback if they receive an event without configuration.
- Table data should be stored in English. UI localization should happen outside this dimension.

## Initial Events

- Intraday Radar: `promo_started`, `promo_ended`, `regular_price_increase`, `regular_price_decrease`, `promo_price_increase`, `promo_price_decrease`.
- Executive signals: `brand_over_market`, `brand_under_market`, `sku_price_gap`, `driver_sku_detected`, `promo_price_break`.
- Historical compatibility: `price_increase`, `price_decrease`, `promo_detected`, `promo_intensity_spike`, `promo_intensity_drop`.
