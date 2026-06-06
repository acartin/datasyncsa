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
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Tabs } from "@/components/ui/tabs";
import { changeIndicator, changeToneClass, showHeaderMetrics } from "@/lib/event-presentation";
import { friendlyApiError } from "@/lib/feedback";
import { IntradayProductDetailPayload, IntradayRadarEvent } from "@/lib/pricing-types";
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

function currency(value: unknown) {
  if (typeof value !== "number") return "-";
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function percent(value: unknown) {
  if (typeof value !== "number") return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function points(value: unknown) {
  if (typeof value !== "number") return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(0)} pts`;
}

function sourceFromValue(value?: string): ProductIntelligenceSource {
  if (value === "radar" || value === "signals" || value === "search" || value === "comparison") return value;
  return "all";
}

type ProductIntelligenceContext = {
  campaignId?: string;
  dateKey?: string;
  chain?: string;
  historyDays?: string;
  source?: string;
  routeBase?: string;
  viewMode?: "event" | "product";
};

const analysisTabs = [
  { id: "summary", label: "Event Overview" },
  { id: "evidence", label: "Store Evidence" },
  { id: "chains", label: "Product Across Chains" },
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
  if (!isStoreAveragePriceEvent(event)) return null;
  const eventStoreCount = event?.available_locations ?? event?.visible_locations ?? event?.observed_locations ?? null;
  const count = typeof eventStoreCount === "number" && eventStoreCount > 0 ? eventStoreCount : storeCount;
  if (count <= 1) return null;
  return `Average across ${count} stores`;
}

function valueForEvent(event: IntradayRadarEvent | null, value: number | null) {
  if (!event) return "-";
  if (event.presentation?.value_format === "percent" || event.event_area === "promotion") {
    return `${(value ?? 0).toFixed(1)}%`;
  }
  return currency(value);
}

function changeForEvent(event: IntradayRadarEvent | null) {
  if (!event || typeof event.previous_value !== "number" || typeof event.current_value !== "number") return "-";
  const delta = event.current_value - event.previous_value;
  if (event.presentation?.change_format === "points" || event.event_area === "promotion") return points(delta);
  if (event.previous_value === 0) return currency(delta);
  return percent((delta / event.previous_value) * 100);
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

function headerProductUrl(payload: IntradayProductDetailPayload, event: IntradayRadarEvent | null) {
  if (event?.product_url) return event.product_url;
  const eventChain = event?.chain ?? payload.product?.chain;
  const matchingChain = payload.chain_snapshot.find((record) => record.chain === eventChain && record.product_url);
  return matchingChain?.product_url ?? payload.product?.product_url ?? null;
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
        <span className="text-border-2">/</span>
        <span>{product.brand}</span>
        <span className="text-border-2">/</span>
        <span className="font-medium text-foreground">{product.product}</span>
      </div>

      <Card className={cn("border-t-2", eventBorderClass(event))}>
        <CardContent className="flex flex-col gap-5 p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-ink-secondary">{eventTitle(event)}</div>
              <div className="text-[11px] text-ink-muted">{compactDate(event?.date_key ?? product.date_key)}</div>
            </div>
            <h1 className="max-w-5xl text-xl font-light leading-snug tracking-[-0.01em]">{product.product}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-ink-muted">
              <ChainTag chain={event?.chain ?? product.chain} />
              <span>{product.brand}</span>
              <span className="text-border-2">/</span>
              <span>
                {product.content_quantity ?? "-"} {product.content_unit ?? ""}
              </span>
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
          {showHeaderMetrics(event) ? (
            <div className="grid overflow-hidden rounded-lg border border-border-2 text-center text-sm sm:grid-cols-3">
              <div className="min-w-32 border-b border-border p-4 sm:border-b-0 sm:border-r">
                <div className="mb-1 text-[10px] uppercase tracking-[0.07em] text-ink-muted">{metricLabels.previous}</div>
                <div className="font-mono text-lg font-normal">{valueForEvent(event, event?.previous_value ?? null)}</div>
              </div>
              <div className="min-w-32 border-b border-border p-4 sm:border-b-0 sm:border-r">
                <div className="mb-1 text-[10px] uppercase tracking-[0.07em] text-ink-muted">{metricLabels.current}</div>
                <div className="font-mono text-lg font-normal">{valueForEvent(event, event?.current_value ?? null)}</div>
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
        <Tabs items={analysisTabs} value={activeTab} onValueChange={setActiveTab} />
      </div>

      {activeTab === "summary" ? <section className="space-y-4">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-[13px] font-medium">Price timeline</div>
                <div className="mt-1 text-[11px] text-ink-muted">Regular and promotional prices across chains.</div>
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
            <div className="text-[13px] font-medium">Related events</div>
            <div className="mt-1 text-[11px] text-ink-muted">Filtered by the selected chains and chart period.</div>
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
                <div className="text-[13px] font-medium">Store-level evidence</div>
                <div className="mt-1 text-[11px] text-ink-muted">Current closed-day captures for the event product and chain.</div>
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
          <h2 className="text-lg font-medium">Product Across Chains</h2>
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
    </div>
  );
}

export const ProductIntelligencePage = IntradayProductPage;
