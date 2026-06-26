"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowDownRight,
  ArrowUpRight,
  ExternalLink,
  GitCompare,
  Minus,
} from "lucide-react";
import { ChainTag } from "@/components/market-watch/chain-tag";
import { IntradayProductChainGrid, IntradayProductEventsGrid, IntradayProductStoreEvidenceGrid } from "@/components/market-watch/intraday-product-grids";
import { ProductNormalPromoPriceCharts } from "@/components/market-watch/product-history-chart";
import { ProductVisual } from "@/components/market-watch/product-visual";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Tabs } from "@/components/ui/tabs";
import { changeIndicator, changeToneClass, formatEventChangeValue, formatEventValue, showHeaderMetrics } from "@/lib/event-presentation";
import { friendlyApiError } from "@/lib/feedback";
import { AvailabilityLocationChange, IntradayProductDetailPayload, IntradayRadarEvent } from "@/lib/pricing-types";
import { cn } from "@/lib/utils";

type ProductIntelligenceSource = "radar" | "signals" | "search" | "comparison" | "all";

function compactDate(value: unknown) {
  const text = String(value ?? "");
  if (!/^\d{8}$/.test(text)) return text || "-";
  return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
}

function formatDateKeyLabel(value: number) {
  const text = String(value);
  if (!/^\d{8}$/.test(text)) return text;
  return `${text.slice(6, 8)}-${text.slice(4, 6)}-${text.slice(0, 4)}`;
}

function formatDDMMYYYY(value: unknown) {
  const text = String(value ?? "");
  if (!/^\d{8}$/.test(text)) return text || "-";
  return `${text.slice(6, 8)}-${text.slice(4, 6)}-${text.slice(0, 4)}`;
}

function ProductIdentifier({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-[6px] border border-border-2 bg-surface-2 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-ink-secondary">
      GTIN
      <code className="select-all font-mono text-[11px] font-normal tracking-normal text-foreground">{value}</code>
    </span>
  );
}

function EventIdentifier({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-[6px] border border-border-2 bg-surface-2 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-ink-secondary">
      Event ID
      <code className="select-all font-mono text-[11px] font-normal tracking-normal text-foreground">{value}</code>
    </span>
  );
}

function numericValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function quantityLabel(value: unknown) {
  const number = numericValue(value);
  if (number === null) return "-";
  return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/\.?0+$/, "");
}

function signedCount(value: unknown) {
  const number = numericValue(value);
  if (number === null) return "-";
  return number > 0 ? `+${number}` : String(number);
}

function availabilitySummary(event: IntradayRadarEvent | null) {
  return event?.evidence?.availability_change_summary ?? null;
}

function availabilityLocations(event: IntradayRadarEvent | null, key: "recovered_locations" | "lost_locations") {
  const value = event?.evidence?.[key];
  return Array.isArray(value) ? value : [];
}

function hasAvailabilityEvidence(event: IntradayRadarEvent | null) {
  if (!event || event.event_area !== "availability") return false;
  const summary = availabilitySummary(event);
  return Boolean(
    summary ||
    availabilityLocations(event, "recovered_locations").length ||
    availabilityLocations(event, "lost_locations").length ||
    event.evidence?.location_name
  );
}

function AvailabilityLocationList({
  title,
  items,
  empty,
}: {
  title: string;
  items: AvailabilityLocationChange[];
  empty: string;
}) {
  return (
    <div className="rounded-md border border-border-2">
      <div className="border-b border-border-2 px-3 py-2 text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">{title}</div>
      <div className="divide-y divide-border-2">
        {items.length ? items.slice(0, 8).map((item) => (
          <div key={`${item.location_key ?? item.location_name}-${item.previous_qty}-${item.current_qty}`} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-[11px]">
            <div className="min-w-0">
              <div className="font-medium text-foreground">{item.location_name ?? item.location_code ?? item.location_key ?? "-"}</div>
              <div className="mt-0.5 text-ink-muted">{[item.province, item.canton].filter(Boolean).join(" / ")}</div>
            </div>
            <div className="font-mono text-foreground">{quantityLabel(item.previous_qty)} -&gt; {quantityLabel(item.current_qty)}</div>
          </div>
        )) : (
          <div className="px-3 py-2 text-[11px] text-ink-muted">{empty}</div>
        )}
        {items.length > 8 ? <div className="px-3 py-2 text-[11px] text-ink-muted">{items.length - 8} more stores</div> : null}
      </div>
    </div>
  );
}

function AvailabilityChangePanel({
  event,
  mode,
}: {
  event: IntradayRadarEvent | null;
  mode: "overview" | "evidence";
}) {
  if (!hasAvailabilityEvidence(event)) return null;

  const summary = availabilitySummary(event);
  const recovered = availabilityLocations(event, "recovered_locations");
  const lost = availabilityLocations(event, "lost_locations");
  const isStoreEvent = event?.event_type === "store_offer_became_available" || event?.event_type === "store_offer_became_unavailable";
  const previousAvailable = summary?.previous_available_locations ?? numericValue(event?.previous_value);
  const currentAvailable = summary?.current_available_locations ?? numericValue(event?.current_value);
  const delta = summary?.available_locations_delta ?? (previousAvailable !== null && currentAvailable !== null ? currentAvailable - previousAvailable : null);
  const previousQty = summary?.previous_source_available_quantity ?? event?.evidence?.previous_source_available_quantity ?? event?.previous_value;
  const currentQty = summary?.current_source_available_quantity ?? event?.evidence?.current_source_available_quantity ?? event?.current_value;

  return (
    <Card>
      <CardHeader>
        <div className="text-[13px] font-medium">Availability change</div>
        <div className="mt-1 text-[11px] text-ink-muted">
          {isStoreEvent ? "Store-level availability transition from the previous closed day." : "Net chain-level availability change with the stores that explain the movement."}
        </div>
      </CardHeader>
      <CardContent>
        {isStoreEvent ? (
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-md border border-border-2 px-3 py-2">
              <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Store</div>
              <div className="mt-1 text-sm font-medium">{event?.evidence?.location_name ?? "-"}</div>
            </div>
            <div className="rounded-md border border-border-2 px-3 py-2">
              <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Previous qty</div>
              <div className="mt-1 font-mono text-sm">{quantityLabel(previousQty)}</div>
            </div>
            <div className="rounded-md border border-border-2 px-3 py-2">
              <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Current qty</div>
              <div className="mt-1 font-mono text-sm">{quantityLabel(currentQty)}</div>
            </div>
          </div>
        ) : (
          <>
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-md border border-border-2 px-3 py-2">
                <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Previous available</div>
                <div className="mt-1 font-mono text-lg">{quantityLabel(previousAvailable)}</div>
              </div>
              <div className="rounded-md border border-border-2 px-3 py-2">
                <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Current available</div>
                <div className="mt-1 font-mono text-lg">{quantityLabel(currentAvailable)}</div>
              </div>
              <div className="rounded-md border border-border-2 px-3 py-2">
                <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Net change</div>
                <div className={cn("mt-1 font-mono text-lg", changeToneClass(event))}>{signedCount(delta)}</div>
              </div>
              <div className="rounded-md border border-border-2 px-3 py-2">
                <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Changed stores</div>
                <div className="mt-1 font-mono text-lg">{recovered.length + lost.length}</div>
              </div>
            </div>
            {mode === "evidence" ? (
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <AvailabilityLocationList title="Recovered stores" items={recovered} empty="No recovered stores for this event." />
                <AvailabilityLocationList title="New unavailable stores" items={lost} empty="No newly unavailable stores for this event." />
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function recommendationText(event: IntradayRadarEvent | null) {
  if (!event) return "Select a radar event to review the recommended follow-up.";
  if (event.signal?.recommended_action) return event.signal.recommended_action;
  if (event.event_area === "availability") {
    if (event.event_type === "chain_available_store_count_recovered") {
      return "Validate the recovered and lost stores before treating this as a stable chain-level recovery.";
    }
    if (event.event_type === "chain_available_store_count_dropped") {
      return "Prioritize validation of newly unavailable stores and confirm whether the drop is isolated or spreading.";
    }
    if (event.event_type === "store_offer_became_available") {
      return "Validate the store capture and keep monitoring the chain view before escalating as a broader recovery.";
    }
    if (event.event_type === "store_offer_became_unavailable") {
      return "Validate the store capture and check whether nearby stores or the same chain show the same transition.";
    }
  }
  if (event.event_area === "promotion") {
    return "Validate the promotion evidence and compare against related products before deciding whether a response is needed.";
  }
  return "Review the event metrics, store evidence, and chain comparison before taking a pricing action.";
}

function signalText(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function RecommendationPanel({ event }: { event: IntradayRadarEvent | null }) {
  const signal = event?.signal ?? null;
  const summary = signalText(signal?.summary);
  const businessReading = signalText(signal?.business_reading);
  const recommendedAction = signalText(signal?.recommended_action) ?? recommendationText(event);
  const hasSynthesis = Boolean(summary || businessReading || signalText(signal?.headline));

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-[13px] font-medium">Recommendations</div>
            <div className="mt-1 text-[11px] text-ink-muted">Executive synthesis and operational next step for this radar event.</div>
          </div>
          {signal?.llm_provider ? (
            <span className="inline-flex items-center rounded-[6px] border border-border-2 bg-surface-2 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">
              {signal.llm_provider}
              {signal.llm_model ? <span className="ml-1 normal-case tracking-normal text-foreground">{signal.llm_model}</span> : null}
            </span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {hasSynthesis ? (
          <div className="rounded-md border border-border-2 bg-card px-4 py-3">
            <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Executive synthesis</div>
            {signalText(signal?.headline) ? <div className="mt-2 text-sm font-medium text-foreground">{signalText(signal?.headline)}</div> : null}
            {summary ? <p className="mt-2 text-sm leading-6 text-ink-secondary">{summary}</p> : null}
          </div>
        ) : null}
        {businessReading ? (
          <div className="rounded-md border border-border-2 bg-card px-4 py-3">
            <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Business reading</div>
            <p className="mt-2 text-sm leading-6 text-ink-secondary">{businessReading}</p>
          </div>
        ) : null}
        <div className="rounded-md border border-border-2 bg-surface-2 px-4 py-3 text-sm leading-6 text-foreground">
          <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Recommended action</div>
          {recommendedAction}
        </div>
        {signal?.llm_prompt_version ? (
          <div className="text-[10px] text-ink-muted">Prompt version: {signal.llm_prompt_version}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function sourceFromValue(value?: string): ProductIntelligenceSource {
  if (value === "radar" || value === "signals" || value === "search" || value === "comparison") return value;
  return "all";
}

type ProductIntelligenceContext = {
  campaignId?: string;
  dateKey?: string;
  chain?: string;
  eventId?: string;
  historyDays?: string;
  source?: string;
  routeBase?: string;
  viewMode?: "event" | "product";
};

const analysisTabs = [
  { id: "summary", label: "Event Overview" },
  { id: "evidence", label: "Store Evidence" },
  { id: "chains", label: "Product Across Chains" },
  { id: "recommendations", label: "Recommendations" },
];

const productAnalysisTabs = [
  { id: "summary", label: "Product Overview" },
  { id: "evidence", label: "Store Coverage" },
  { id: "chains", label: "Radar Events" },
];

type PriceMode = "regular" | "promo" | "both";
type EvidenceFilter = "all" | "available" | "promo" | "unavailable";

const periodOptions = [
  { label: "7 days", days: "7" },
  { label: "30 days", days: "30" },
  { label: "90 days", days: "90" },
  { label: "365 days", days: "365" },
];

function chainOptions(payload: IntradayProductDetailPayload, preferredChain?: string) {
  const chains = Array.from(
    new Set([
      ...(preferredChain ? [preferredChain] : []),
      ...payload.price_history.map((point) => point.chain),
      ...payload.chain_snapshot.map((item) => item.chain),
    ].filter(Boolean))
  );
  return chains;
}

function selectedEvent(payload: IntradayProductDetailPayload, context: ProductIntelligenceContext) {
  if (context.viewMode === "product" && !context.dateKey && !context.chain) return null;
  const dateKey = context.dateKey ? Number(context.dateKey) : undefined;
  return (
    payload.events.find((event) => context.eventId && event.event_id === context.eventId) ??
    payload.events.find((event) => (!dateKey || event.date_key === dateKey) && (!context.chain || event.chain === context.chain)) ??
    payload.events.find((event) => !context.chain || event.chain === context.chain) ??
    payload.events[0] ??
    null
  );
}

function eventTitle(event: IntradayRadarEvent | null) {
  if (!event) return "PRODUCT INTELLIGENCE";
  return event.presentation?.display_label ?? event.event_type.replaceAll("_", " ").toUpperCase();
}

function eventBadgeLabel(event: IntradayRadarEvent | null) {
  const label = eventTitle(event);
  return label
    .split(" ")
    .map((word) => {
      if (word.length <= 3 && word === word.toUpperCase()) return word;
      const lower = word.toLowerCase();
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(" ");
}

function isStoreAveragePriceEvent(event: IntradayRadarEvent | null) {
  return event?.event_type === "regular_price_increase" || event?.event_type === "regular_price_decrease";
}

function metricLabelsForEvent(event: IntradayRadarEvent | null) {
  if (isStoreAveragePriceEvent(event)) {
    return {
      previous: "Previous avg",
      current: "Current avg",
      change: event?.presentation?.metric_labels?.change ?? "Change",
    };
  }

  return event?.presentation?.metric_labels ?? {
    previous: "Previous",
    current: "Current",
    change: "Change",
  };
}

function metricContextForEvent(event: IntradayRadarEvent | null, storeCount: number) {
  if (event?.event_area === "availability") {
    const visible = event.visible_locations ?? event.previous_value ?? null;
    const available = event.available_locations ?? event.current_value ?? null;
    if (typeof visible === "number" && typeof available === "number") {
      return `${available} of ${visible} stores available`;
    }
  }
  if (!isStoreAveragePriceEvent(event)) return null;
  const eventStoreCount = event?.available_locations ?? event?.visible_locations ?? event?.observed_locations ?? null;
  const count = typeof eventStoreCount === "number" && eventStoreCount > 0 ? eventStoreCount : storeCount;
  if (count <= 1) return null;
  return `Average across ${count} stores`;
}

function valueForEvent(event: IntradayRadarEvent | null, value: number | null, slot: "previous" | "current") {
  return formatEventValue(event, value, slot);
}

function changeForEvent(event: IntradayRadarEvent | null) {
  return formatEventChangeValue(event);
}

function ChangeTrendIcon({ event }: { event: IntradayRadarEvent | null }) {
  const indicator = changeIndicator(event);
  if (indicator === "up") return <ArrowUpRight className="h-4 w-4" />;
  if (indicator === "down") return <ArrowDownRight className="h-4 w-4" />;
  return <Minus className="h-4 w-4" />;
}

function eventBorderClass(event: IntradayRadarEvent | null) {
  const token = event?.presentation?.accent_token;
  if (token === "danger") return "border-t-semantic-red";
  if (token === "warning") return "border-t-semantic-amber";
  if (token === "success") return "border-t-semantic-green";
  return "border-t-border-2";
}

function eventBadgeClass(event: IntradayRadarEvent | null) {
  const token = event?.presentation?.accent_token;
  if (token === "danger") return "border-[var(--red)] bg-[var(--red-bg)] text-[var(--red-text)]";
  if (token === "warning") return "border-[var(--amber)] bg-[var(--amber-bg)] text-[var(--amber-text)]";
  if (token === "success") return "border-[var(--green)] bg-[var(--green-bg)] text-[var(--green-text)]";
  return "border-border-2 bg-surface-3 text-ink-secondary";
}

function eventBadgeIconClass(event: IntradayRadarEvent | null) {
  const token = event?.presentation?.accent_token;
  if (token === "danger") return "bg-semantic-red text-white";
  if (token === "warning") return "bg-semantic-amber text-white";
  if (token === "success") return "bg-semantic-green text-white";
  return "bg-ink-secondary text-white";
}

function EventTypeBadge({ event }: { event: IntradayRadarEvent | null }) {
  if (!event) return null;
  return (
    <span
      className={cn(
        "inline-flex min-h-8 items-center gap-2 rounded-[6px] border px-2.5 py-1 text-[12px] font-semibold leading-none shadow-sm",
        eventBadgeClass(event)
      )}
    >
      <span className={cn("flex h-5 w-5 shrink-0 items-center justify-center rounded-[5px]", eventBadgeIconClass(event))}>
        <ChangeTrendIcon event={event} />
      </span>
      <span>{eventBadgeLabel(event)}</span>
    </span>
  );
}

function headerProductUrl(payload: IntradayProductDetailPayload, event: IntradayRadarEvent | null) {
  if (event?.product_url) return event.product_url;
  const eventChain = event?.chain ?? payload.product?.chain;
  const matchingChain = payload.chain_snapshot.find((record) => record.chain === eventChain && record.product_url);
  return matchingChain?.product_url ?? payload.product?.product_url ?? null;
}

function productImages(payload: IntradayProductDetailPayload) {
  return Array.from(
    new Set([
      payload.product?.image_url,
      ...payload.chain_snapshot.map((record) => record.image_url),
      ...payload.store_evidence.map((record) => record.image_url),
    ].filter((value): value is string => Boolean(value)))
  );
}

function productRouteBase(context: ProductIntelligenceContext) {
  return context.routeBase ?? "/pricing/products";
}

function backNavigation(source: ProductIntelligenceSource) {
  if (source === "signals") {
    return {
      href: "/pricing/executive-signals",
      label: "Executive signals",
    };
  }
  return {
    href: "/pricing/intraday-radar",
    label: "Price radar",
  };
}

function periodHref(productKey: string, params: ProductIntelligenceContext, days: string) {
  const search = new URLSearchParams();
  if (params.campaignId) search.set("campaign_id", params.campaignId);
  if (params.dateKey) search.set("date_key", params.dateKey);
  if (params.chain) search.set("chain", params.chain);
  if (params.source) search.set("source", params.source);
  search.set("history_days", days);
  return `${productRouteBase(params)}/${encodeURIComponent(productKey)}?${search.toString()}`;
}

function evidenceFilterLabel(filter: EvidenceFilter) {
  if (filter === "available") return "Available";
  if (filter === "promo") return "With promo";
  if (filter === "unavailable") return "Unavailable";
  return "All stores";
}

export function IntradayProductPage({
  payload,
  context = {},
}: {
  payload: IntradayProductDetailPayload;
  context?: ProductIntelligenceContext;
}) {
  const [currentPayload, setCurrentPayload] = useState(payload);
  const [activeHistoryDays, setActiveHistoryDays] = useState(context.historyDays ?? "30");
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const requestRef = useRef<AbortController | null>(null);
  const product = currentPayload.product;
  const source = sourceFromValue(context.source);
  const navigation = backNavigation(source);

  useEffect(() => {
    requestRef.current?.abort();
    requestRef.current = null;
    setCurrentPayload(payload);
    setActiveHistoryDays(context.historyDays ?? "30");
    setHistoryError(null);
    setIsHistoryLoading(false);
  }, [payload, context.historyDays]);

  useEffect(() => () => requestRef.current?.abort(), []);

  if (!product) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline">
          <Link href={navigation.href}>
            <ArrowLeft className="h-4 w-4" />
            {navigation.label}
          </Link>
        </Button>
        <Card>
          <CardContent>
            <EmptyState title="Product not found" description="No consolidated daily data is available for this product." />
          </CardContent>
        </Card>
      </div>
    );
  }

  const productKey = product.product_key;
  const isProductMode = context.viewMode === "product";

  const chains = chainOptions(currentPayload, context.chain ?? product.chain ?? undefined);
  const initialSelectedChains = context.chain && chains.includes(context.chain) ? [context.chain] : chains;
  const chainSelectionKey = initialSelectedChains.join("|");
  const [selectedChains, setSelectedChains] = useState<string[]>(initialSelectedChains);
  const [priceMode, setPriceMode] = useState<PriceMode>("both");
  const [activeTab, setActiveTab] = useState("summary");
  const [evidenceFilter, setEvidenceFilter] = useState<EvidenceFilter>("all");

  useEffect(() => {
    setSelectedChains(initialSelectedChains);
  }, [productKey, context.chain, chainSelectionKey]);

  const displayedChains = selectedChains;
  const event = selectedEvent(currentPayload, context);
  const productUrl = headerProductUrl(currentPayload, event);
  const images = productImages(currentPayload);
  const hasSku = Boolean(product.gtin || images.length);
  const visibleChainLabel = isProductMode && !context.chain ? `${chains.length} chains monitored` : event?.chain ?? product.chain;
  const activeTabs = isProductMode ? productAnalysisTabs : analysisTabs;
  const heroTitle = product.product;
  const heroSubtitle = isProductMode ? "Product intelligence" : eventTitle(event);
  const heroDate = compactDate(event?.date_key ?? product.date_key);
  const showEventMetrics = !isProductMode && showHeaderMetrics(event);
  const visibleDateKeys = new Set(
    currentPayload.price_history
      .filter((point) => displayedChains.includes(point.chain))
      .map((point) => Number(point.date_key))
      .filter((value) => Number.isFinite(value))
  );
  const rangeLabel = (() => {
    const sortedDateKeys = Array.from(visibleDateKeys).sort((left, right) => left - right);
    if (!sortedDateKeys.length) return null;
    return `from ${formatDateKeyLabel(sortedDateKeys[0])} to ${formatDateKeyLabel(sortedDateKeys[sortedDateKeys.length - 1])}`;
  })();

  const filteredEvents = currentPayload.events.filter((record) => {
    const inChain = displayedChains.includes(record.chain);
    if (!inChain) return false;
    if (!visibleDateKeys.size) return true;
    const ownDateKey = Number(record.date_key);
    const previousDateKey = Number(record.previous_date_key);
    return visibleDateKeys.has(ownDateKey) || (Number.isFinite(previousDateKey) && visibleDateKeys.has(previousDateKey));
  });
  const productEvents = currentPayload.events.filter((record) => {
    if (!visibleDateKeys.size) return true;
    const ownDateKey = Number(record.date_key);
    const previousDateKey = Number(record.previous_date_key);
    return visibleDateKeys.has(ownDateKey) || (Number.isFinite(previousDateKey) && visibleDateKeys.has(previousDateKey));
  });
  const storeEvidence = currentPayload.store_evidence ?? [];
  const metricLabels = metricLabelsForEvent(event);
  const metricContext = metricContextForEvent(event, storeEvidence.length);
  const filteredStoreEvidence = storeEvidence.filter((record) => {
    if (evidenceFilter === "available") return record.is_available === true;
    if (evidenceFilter === "promo") return record.promo_detected === true || typeof record.spot_price_amount === "number";
    if (evidenceFilter === "unavailable") return record.is_available === false;
    return true;
  });
  const storeCounts = {
    total: storeEvidence.length,
    listed: storeEvidence.filter((record) => record.is_listed).length,
    available: storeEvidence.filter((record) => record.is_available).length,
    promo: storeEvidence.filter((record) => record.promo_detected || typeof record.spot_price_amount === "number").length,
  };

  function toggleChain(chain: string) {
    setSelectedChains((current) => {
      if (current.includes(chain) && current.length === 1) return current;
      if (current.includes(chain)) return current.filter((item) => item !== chain);
      return [...current, chain];
    });
  }

  async function changePeriod(days: string) {
    if (days === activeHistoryDays) return;
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    const previousDays = activeHistoryDays;
    setActiveHistoryDays(days);
    setHistoryError(null);
    setIsHistoryLoading(true);

    try {
      const response = await fetch(`/api/pricing/products/${encodeURIComponent(productKey)}?${new URLSearchParams({
        ...(context.campaignId ? { campaign_id: context.campaignId } : {}),
        ...(context.dateKey ? { date_key: context.dateKey } : {}),
        ...(context.chain ? { chain: context.chain } : {}),
        history_days: days,
      }).toString()}`, {
        cache: "no-store",
        signal: controller.signal,
      });
      const nextPayload = await response.json().catch(() => undefined);
      if (!response.ok) {
        throw new Error(friendlyApiError(nextPayload));
      }
      if (requestRef.current !== controller) return;
      setCurrentPayload(nextPayload as IntradayProductDetailPayload);
      window.history.replaceState(null, "", periodHref(productKey, context, days));
    } catch (error) {
      if (controller.signal.aborted) return;
      setActiveHistoryDays(previousDays);
      setHistoryError(error instanceof Error ? error.message : "The period could not be updated.");
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setIsHistoryLoading(false);
      }
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <Button asChild variant="outline" className="h-8">
          <Link href={navigation.href}>
            <ArrowLeft className="h-4 w-4" />
            {navigation.label}
          </Link>
        </Button>
      </div>

      <Card className={cn("border-t-2", isProductMode ? "border-t-border-2" : eventBorderClass(event))}>
        <CardContent className="flex flex-col gap-5 p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 flex-col gap-5 sm:flex-row sm:items-center">
            {isProductMode ? <ProductVisual hasSku={hasSku} images={images} size="md" /> : null}
            <div className="min-w-0">
	            <div className="mb-3 flex flex-wrap items-center gap-2">
	              {isProductMode ? (
	                <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-ink-secondary">{heroSubtitle}</div>
	              ) : (
	                <EventTypeBadge event={event} />
	              )}
	              <div className="text-[11px] text-ink-muted">{heroDate}</div>
	              {!isProductMode ? <EventIdentifier value={event?.event_id} /> : null}
	            </div>
            <h1 className={cn("max-w-5xl font-light leading-snug", isProductMode ? "text-2xl" : "text-3xl")}>{heroTitle}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-ink-muted">
              {visibleChainLabel ? <ChainTag chain={visibleChainLabel} /> : null}
              <span>{product.brand}</span>
              <span className="text-border-2">/</span>
              <span>
                {product.content_quantity ?? "-"} {product.content_unit ?? ""}
              </span>
              <ProductIdentifier value={product.gtin} />
              <span className="text-border-2">/</span>
              <span>Campaign {event?.campaign_id ?? product.campaign_id}</span>
              {productUrl ? (
                <>
                  <span className="text-border-2">/</span>
                  <a
                    href={productUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-[6px] border border-border-2 px-2 py-1 text-foreground transition-colors hover:border-foreground hover:text-semantic-blue"
                  >
                    View product
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </>
              ) : null}
            </div>
            </div>
          </div>
          {showEventMetrics ? (
            <div className="grid overflow-hidden rounded-lg border border-border-2 text-center text-sm sm:grid-cols-3">
              <div className="min-w-32 border-b border-border p-4 sm:border-b-0 sm:border-r">
                <div className="mb-1 text-[10px] uppercase tracking-[0.07em] text-ink-muted">{metricLabels.previous}</div>
                <div className="font-mono text-lg font-normal">{valueForEvent(event, event?.previous_value ?? null, "previous")}</div>
              </div>
              <div className="min-w-32 border-b border-border p-4 sm:border-b-0 sm:border-r">
                <div className="mb-1 text-[10px] uppercase tracking-[0.07em] text-ink-muted">{metricLabels.current}</div>
                <div className="font-mono text-lg font-normal">{valueForEvent(event, event?.current_value ?? null, "current")}</div>
              </div>
              <div className="min-w-32 p-4">
                <div className="mb-1 text-[10px] uppercase tracking-[0.07em] text-ink-muted">{metricLabels.change}</div>
                <div className={cn("inline-flex items-center gap-1 font-mono text-lg font-medium", changeToneClass(event))}>
                  <ChangeTrendIcon event={event} />
                  <span>{changeForEvent(event)}</span>
                </div>
              </div>
              {metricContext ? (
                <div className="border-t border-border px-4 py-2 text-[11px] text-ink-muted sm:col-span-3">
                  {metricContext}
                </div>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="border-b border-border-2">
        <Tabs items={activeTabs} value={activeTab} onValueChange={setActiveTab} />
      </div>

      {activeTab === "summary" ? <section className="space-y-4">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-[13px] font-medium">{isProductMode ? "Product price history" : "Price timeline"}</div>
                <div className="mt-1 text-[11px] text-ink-muted">
                  {isProductMode ? "Regular and promotional price behavior across monitored chains." : "Regular and promotional prices around this radar event."}
                </div>
              </div>
              <div className="flex flex-wrap gap-3 border-b border-border-2 pb-px">
                {(["both", "regular", "promo"] as PriceMode[]).map((mode) => (
                  <Button key={mode} variant="chip" data-active={priceMode === mode} className="capitalize" onClick={() => setPriceMode(mode)}>
                    {mode}
                  </Button>
                ))}
              </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <div className="mr-1 w-12 text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Period</div>
              {periodOptions.map((option) => (
                <Button
                  key={option.days}
                  type="button"
                  variant="chip"
                  data-active={activeHistoryDays === option.days}
                  disabled={isHistoryLoading && activeHistoryDays === option.days}
                  onClick={() => changePeriod(option.days)}
                >
                  {option.label}
                </Button>
              ))}
              {isHistoryLoading ? (
                <span className="text-[10px] text-ink-muted">Updating…</span>
              ) : null}
              {rangeLabel && (
                <span className="text-[10px] text-ink-muted">{rangeLabel}</span>
              )}
            </div>
            {historyError ? (
              <Alert variant="error" title="Could not update period" className="mt-3">
                {historyError}
              </Alert>
            ) : null}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <div className="mr-1 w-12 text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Chains</div>
              <Button
                variant="chip"
                data-active={selectedChains.length === chains.length || selectedChains.length === 0}
                onClick={() => setSelectedChains(selectedChains.length === chains.length ? [] : chains)}
              >
                {selectedChains.length === chains.length ? "Clear all" : "All chains"}
              </Button>
              {chains.map((chain) => (
                <Button key={chain} variant="chip" data-active={displayedChains.includes(chain)} onClick={() => toggleChain(chain)}>
                  {chain}
                </Button>
              ))}
            </div>
          </CardHeader>
          <CardContent>
            <ProductNormalPromoPriceCharts history={currentPayload.price_history} selectedChains={displayedChains} priceMode={priceMode} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="text-[13px] font-medium">{isProductMode ? "Latest radar events" : "Related events"}</div>
            <div className="mt-1 text-[11px] text-ink-muted">
              {isProductMode ? "Recent price, promotion and availability signals for this product." : "Filtered by the selected chains and chart period."}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <IntradayProductEventsGrid records={filteredEvents} />
          </CardContent>
        </Card>
      </section> : null}

      {activeTab === "evidence" ? <section className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-lg border border-border-2 bg-card px-4 py-3">
            <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Stores</div>
            <div className="mt-1 font-mono text-xl">{storeCounts.total}</div>
          </div>
          <div className="rounded-lg border border-border-2 bg-card px-4 py-3">
            <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Listed</div>
            <div className="mt-1 font-mono text-xl">{storeCounts.listed}</div>
          </div>
          <div className="rounded-lg border border-border-2 bg-card px-4 py-3">
            <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Available</div>
            <div className="mt-1 font-mono text-xl">{storeCounts.available}</div>
          </div>
          <div className="rounded-lg border border-border-2 bg-card px-4 py-3">
            <div className="text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">With promo</div>
            <div className="mt-1 font-mono text-xl">{storeCounts.promo}</div>
          </div>
        </div>
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-[13px] font-medium">{isProductMode ? "Store coverage" : "Store-level evidence"}</div>
                <div className="mt-1 text-[11px] text-ink-muted">
                  {isProductMode ? "Latest closed-day listing, availability and promo coverage by store." : "Current closed-day captures for the event product and chain."}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {(["all", "available", "promo", "unavailable"] as EvidenceFilter[]).map((filter) => (
                  <Button key={filter} variant="chip" data-active={evidenceFilter === filter} onClick={() => setEvidenceFilter(filter)}>
                    {evidenceFilterLabel(filter)}
                  </Button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <IntradayProductStoreEvidenceGrid
              records={filteredStoreEvidence}
              navigationContext={{
                productKey: product.product_key,
                campaignId: context.campaignId,
                dateKey: context.dateKey,
                chain: event?.chain ?? product.chain ?? undefined,
                historyDays: context.historyDays ?? "30",
              }}
            />
          </CardContent>
        </Card>
      </section> : null}

      {activeTab === "chains" ? <section className="space-y-4">
        <div className="flex items-center gap-2">
          <GitCompare className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-medium">{isProductMode ? "Radar Events" : "Product Across Chains"}</h2>
        </div>
        <Card>
          <CardHeader>
            <div className="text-[13px] font-medium">Current chain snapshot</div>
            <div className="mt-1 text-[11px] text-ink-muted">Latest closed-day price, promo and availability by chain for this product.</div>
          </CardHeader>
          <CardContent className="p-0">
            <IntradayProductChainGrid records={currentPayload.chain_snapshot} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div className="text-[13px] font-medium">Events across chains</div>
            <div className="mt-1 text-[11px] text-ink-muted">Related price and promotion movements for this product across the selected period.</div>
          </CardHeader>
          <CardContent className="p-0">
            <IntradayProductEventsGrid records={productEvents} />
          </CardContent>
        </Card>
      </section> : null}

      {activeTab === "recommendations" ? <section className="space-y-4">
        <RecommendationPanel event={event} />
        <AvailabilityChangePanel event={event} mode="evidence" />
      </section> : null}
    </div>
  );
}

export const ProductIntelligencePage = IntradayProductPage;
