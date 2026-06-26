begin;

with guidance(event_type, llm_guidance) as (
  values
    (
      'regular_price_decrease',
      'Explain this as an observed regular price decrease for the product in the chain. Mention previous price, current price, percent change, observed store coverage, and whether this creates a competitive pressure or an opportunity. Do not call it a promotion unless promotion evidence is present.'
    ),
    (
      'regular_price_increase',
      'Explain this as an observed regular price increase for the product in the chain. Mention previous price, current price, percent change, observed store coverage, and the commercial risk or monitoring action. Do not infer margin, demand, or sales impact.'
    ),
    (
      'sku_price_gap',
      'Explain this as a SKU-level price gap against the best observed market price. Name the product, chain, observed current price, best market reference, and gap when present. Recommend validating the store evidence and deciding whether the gap is acceptable or requires action.'
    ),
    (
      'brand_over_market',
      'Explain this as a brand-level position above the observed market reference for the chain. Emphasize the gap, the chain, and the need to inspect SKU drivers before changing price. Do not imply market share, sales, margin, elasticity, or customer behavior.'
    ),
    (
      'brand_under_market',
      'Explain this as a brand-level position below the observed market reference for the chain. Emphasize whether this looks like an aggressive position or a monitoring point. Do not imply sales, margin, elasticity, or customer behavior.'
    ),
    (
      'driver_sku_detected',
      'Explain that a small group of SKUs is driving a material part of the observed gap. Mention the driver products and contribution metrics when present. Recommend reviewing those SKUs first instead of broad portfolio action.'
    ),
    (
      'promo_price_break',
      'Explain this as a promotional price break supported by observed price evidence. Focus on the promoted product, chain, discount or gap metrics, and the validation or response action. Do not dilute it into a generic price gap.'
    )
)
update public.mkt_dim_market_event_type et
set presentation_config = coalesce(et.presentation_config, '{}'::jsonb)
    || jsonb_build_object('llm_guidance', guidance.llm_guidance),
    updated_at = now()
from guidance
where et.event_type = guidance.event_type;

commit;
