export type SignalFilterOption = {
  id: string;
  label: string;
};

export type ExecutiveSignal = Record<string, unknown> & {
  signal_id: string;
  business_date: string;
  date_key: number;
  client_id: string;
  campaign_id: number;
  campaign: string;
  brand: string;
  chain: string | null;
  signal_type: string;
  signal_status: string;
  severity: string;
  impact_score: number | null;
  confidence_score: number | null;
  headline: string;
  summary: string | null;
  business_reading: string | null;
  recommended_action: string | null;
  notification_status: string | null;
  repeat_count: number | null;
  product_display: string;
  product_key: string | null;
  evidence_product: string | null;
};

export type SignalKpis = {
  total_signals: number;
  high_severity_signals: number;
  new_signals: number;
  active_repeated_signals: number;
  promo_signals: number;
  price_gap_signals: number;
  latest_business_date?: string | null;
};

export type SignalFilters = {
  campaigns: SignalFilterOption[];
  brands: SignalFilterOption[];
  chains: SignalFilterOption[];
  signal_types: SignalFilterOption[];
  severities: SignalFilterOption[];
  statuses: SignalFilterOption[];
};

export type ExecutiveSignalsPayload = {
  client_id: string;
  limit: number;
  offset: number;
  kpis: SignalKpis;
  filters: SignalFilters;
  items: ExecutiveSignal[];
};

export type SkuPriceDriver = Record<string, unknown> & {
  chain: string;
  average_price: number | null;
  best_chain_average_price: number | null;
  best_chain: string | null;
  gap_pct: number | null;
  price_index: number | null;
  price_reading: string | null;
  suggested_action: string | null;
  product_url: string | null;
  image_url: string | null;
  best_chain_url: string | null;
  best_price_image_url: string | null;
};

export type StoreEvidence = Record<string, unknown> & {
  chain: string;
  store: string;
  observed_price: number | null;
  captured_at_cr: string | null;
  promo_detected: boolean | null;
  discount_pct: number | null;
  product_url: string | null;
  image_url: string | null;
};

export type SignalDetailPayload = {
  client_id: string;
  signal: ExecutiveSignal | null;
  drivers: SkuPriceDriver[];
  evidence: StoreEvidence[];
};

export type ExecutiveSignalSearchParams = {
  campaign_id?: string;
  date_from?: string;
  date_to?: string;
  brand?: string;
  chain?: string;
  signal_type?: string;
  severity?: string;
  signal_status?: string;
  q?: string;
  limit?: string;
  offset?: string;
};

export type IntradayRadarEvent = Record<string, unknown> & {
  event_id: string;
  event_area: string;
  event_type: string;
  severity: string;
  presentation?: {
    display_label: string;
    short_label: string;
    description?: string;
    metric_labels: {
      previous: string;
      current: string;
      change: string;
    };
    value_format: string;
    change_format: string;
    direction_semantics: string;
    header_variant: string;
    icon_name: string;
    accent_token: string;
    chart_annotation_label?: string;
    config?: Record<string, unknown>;
  } | null;
  business_date: string;
  date_key: number;
  previous_date_key?: number | null;
  campaign_id: number;
  campaign: string;
  chain: string;
  brand: string;
  product: string;
  content_quantity: number | null;
  content_unit: string | null;
  gtin: string | null;
  product_key: string | null;
  captured_at_cr: string;
  previous_captured_at_cr: string | null;
  previous_value: number | null;
  current_value: number | null;
  change_amount: number | null;
  change_pct: number | null;
  promo_share_pct: number | null;
  discount_pct: number | null;
  observed_locations: number | null;
  visible_locations: number | null;
  available_locations: number | null;
  product_url: string | null;
};

export type IntradayRadarKpis = {
  total_events: number;
  price_events: number;
  promo_events: number;
  high_severity_events: number;
  latest_date_key?: number | null;
  latest_capture?: string | null;
  selected_date_key?: number | null;
  prior_closed_date_key?: number | null;
  current_cr_date_key?: number | null;
};

export type IntradayRadarFilters = {
  campaigns: SignalFilterOption[];
  brands: SignalFilterOption[];
  chains: SignalFilterOption[];
  products: SignalFilterOption[];
  event_areas: SignalFilterOption[];
  severities: SignalFilterOption[];
};

export type IntradayRadarPayload = {
  client_id: string;
  limit: number;
  offset: number;
  kpis: IntradayRadarKpis;
  filters: IntradayRadarFilters;
  items: IntradayRadarEvent[];
};

export type IntradayProductSummary = Record<string, unknown> & {
  product_key: string;
  gtin: string | null;
  brand: string;
  product: string;
  content_quantity: number | null;
  content_unit: string | null;
  campaign_id: number;
  campaign: string;
  chain: string | null;
  date_key: number;
  latest_capture: string | null;
  min_price: number | null;
  max_price: number | null;
  avg_price: number | null;
  max_discount_pct: number | null;
  promo_seen: boolean;
  image_url: string | null;
  product_url: string | null;
};

export type IntradayProductChainSnapshot = Record<string, unknown> & {
  chain: string;
  captured_at_cr: string;
  average_price: number | null;
  average_unit_price: number | null;
  min_price: number | null;
  max_price: number | null;
  promo_detected: boolean | null;
  promo_share_pct: number | null;
  max_discount_pct: number | null;
  visible_locations: number | null;
  available_locations: number | null;
  product_url: string | null;
  image_url: string | null;
};

export type IntradayProductStoreEvidence = Record<string, unknown> & {
  date_key: number;
  chain: string;
  location_key: number | null;
  location_code: string | null;
  location_name: string | null;
  province: string | null;
  canton: string | null;
  district: string | null;
  sales_channel: string | null;
  region_id: string | null;
  captured_at_cr: string;
  is_listed: boolean | null;
  is_available: boolean | null;
  reference_price_amount: number | null;
  spot_price_amount: number | null;
  effective_price_amount: number | null;
  promo_detected: boolean | null;
  discount_pct: number | null;
  available_quantity: number | null;
  product_url: string | null;
  store_context_url: string | null;
};

export type IntradayProductStoreOption = Record<string, unknown> & {
  location_key: number;
  chain: string;
  location_name: string;
  location_code: string | null;
  province: string | null;
  canton: string | null;
  district: string | null;
  sales_channel: string | null;
  region_id: string | null;
};

export type IntradayProductStoreSummary = Record<string, unknown> & {
  product_key: string;
  gtin: string | null;
  brand: string;
  product: string;
  content_quantity: number | null;
  content_unit: string | null;
  campaign_id: number;
  campaign: string;
  chain: string;
  date_key: number;
  latest_capture: string | null;
  current_regular_price: number | null;
  current_promo_price: number | null;
  current_effective_price: number | null;
  promo_detected: boolean | null;
  discount_pct: number | null;
  product_url: string | null;
  image_url: string | null;
};

export type IntradayProductHistoryPoint = Record<string, unknown> & {
  date_key: number;
  chain: string;
  captured_at_cr: string;
  average_price: number | null;
  average_unit_price: number | null;
  promo_detected: boolean | null;
  promo_share_pct: number | null;
  max_discount_pct: number | null;
};

export type IntradayProductDailyPoint = Record<string, unknown> & {
  date_key: number;
  business_date: string;
  chain: string;
  average_price: number | null;
  average_unit_price: number | null;
  gap_pct: number | null;
  price_index: number | null;
  price_reading: string | null;
  suggested_action: string | null;
};

export type IntradayProductPricePoint = Record<string, unknown> & {
  date_key: number;
  previous_date_key?: number | null;
  business_date: string;
  chain: string;
  store?: string | null;
  captured_at_cr: string;
  effective_price_amount: number | null;
  reference_price_amount: number | null;
  promo_price_amount: number | null;
  promo_detected: boolean | null;
  discount_pct: number | null;
};

export type IntradayProductStoreCapture = IntradayProductPricePoint & {
  location_key: number;
  is_listed: boolean | null;
  is_available: boolean | null;
  product_url: string | null;
  store_context_url: string | null;
};

export type IntradayProductDetailPayload = {
  client_id: string;
  product: IntradayProductSummary | null;
  chain_snapshot: IntradayProductChainSnapshot[];
  store_evidence: IntradayProductStoreEvidence[];
  daily_history: IntradayProductDailyPoint[];
  history: IntradayProductHistoryPoint[];
  price_history: IntradayProductPricePoint[];
  events: IntradayRadarEvent[];
};

export type IntradayProductStoreDetailPayload = {
  client_id: string;
  product: IntradayProductStoreSummary | null;
  selected_store: IntradayProductStoreOption | null;
  store_options: IntradayProductStoreOption[];
  price_history: IntradayProductPricePoint[];
  captures: IntradayProductStoreCapture[];
};

export type IntradayRadarSearchParams = {
  campaign_id?: string;
  date_key?: string;
  date_key_from?: string;
  date_key_to?: string;
  date_key_preset?: "today" | "last_day" | "last_week" | "last_month" | "last_quarter";
  history_days?: string;
  brand?: string;
  chain?: string;
  product_key?: string;
  event_area?: string;
  severity?: string;
  q?: string;
  limit?: string;
  offset?: string;
};
