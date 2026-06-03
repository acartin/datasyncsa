"use client";

import Link from "next/link";
import { startTransition, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowDownRight,
  ArrowUpRight,
  ExternalLink,
  GitCompare,
  Minus,
} from "lucide-react";
import { ChainTag } from "@/components/market-watch/chain-tag";
import { IntradayProductChainGrid, IntradayProductEventsGrid } from "@/components/market-watch/intraday-product-grids";
import { ProductNormalPromoPriceCharts } from "@/components/market-watch/product-history-chart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Tabs } from "@/components/ui/tabs";
import { changeIndicator, changeToneClass, showHeaderMetrics } from "@/lib/event-presentation";
import { IntradayProductDetailPayload, IntradayRadarEvent } from "@/lib/pricing-types";
import { cn } from "@/lib/utils";

type ProductIntelligenceSource = "radar" | "signals" | "search" | "comparison" | "all";

function compactDate(value: unknown) {
  const text = String(value ?? "");
  if (!/^\d{8}$/.test(text)) return text || "-";
  return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
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
};

const analysisTabs = [
  { id: "summary", label: "Overview" },
  { id: "position", label: "Market Position" },
];

type PriceMode = "regular" | "promo" | "both";

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

function periodHref(productKey: string, params: ProductIntelligenceContext, days: string) {
  const search = new URLSearchParams();
  if (params.campaignId) search.set("campaign_id", params.campaignId);
  if (params.dateKey) search.set("date_key", params.dateKey);
  if (params.chain) search.set("chain", params.chain);
  if (params.source) search.set("source", params.source);
  search.set("history_days", days);
  return `/pricing/products/${encodeURIComponent(productKey)}?${search.toString()}`;
}

export function IntradayProductPage({
  payload,
  context = {},
}: {
  payload: IntradayProductDetailPayload;
  context?: ProductIntelligenceContext;
}) {
  const product = payload.product;
  const source = sourceFromValue(context.source);
  const router = useRouter();
  if (!product) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline">
          <Link href="/pricing/intraday-radar">
            <ArrowLeft className="h-4 w-4" />
            Price & Promotions Radar
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

  const chains = chainOptions(payload, context.chain ?? product.chain ?? undefined);
  const initialSelectedChains = context.chain && chains.includes(context.chain) ? [context.chain] : chains;
  const initialHistoryDays = context.historyDays ?? "30";
  const [activeHistoryDays, setActiveHistoryDays] = useState(initialHistoryDays);
  const [selectedChains, setSelectedChains] = useState<string[]>(initialSelectedChains);
  const [priceMode, setPriceMode] = useState<PriceMode>("both");
  const [activeTab, setActiveTab] = useState("summary");
  const displayedChains = selectedChains;
  const event = selectedEvent(payload, context);
  const metricLabels = event?.presentation?.metric_labels ?? {
    previous: "Previous",
    current: "Current",
    change: "Change",
  };
  const productUrl = headerProductUrl(payload, event);
  const visibleDateKeys = new Set(
    payload.price_history
      .filter((point) => displayedChains.includes(point.chain))
      .map((point) => Number(point.date_key))
      .filter((value) => Number.isFinite(value))
  );
  const rangeLabel = (() => {
    const dk = product?.date_key;
    if (!dk) return null;
    const s = String(dk);
    const to = new Date(Number(s.slice(0, 4)), Number(s.slice(4, 6)) - 1, Number(s.slice(6, 8)));
    const from = new Date(to);
    from.setDate(from.getDate() - Number(activeHistoryDays) + 1);
    const fmt = (d: Date) =>
      `${String(d.getDate()).padStart(2, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${d.getFullYear()}`;
    return `from ${fmt(from)} to ${fmt(to)}`;
  })();

  const filteredEvents = payload.events.filter((record) => {
    const inChain = displayedChains.includes(record.chain);
    if (!inChain) return false;
    if (!visibleDateKeys.size) return true;
    const ownDateKey = Number(record.date_key);
    const previousDateKey = Number(record.previous_date_key);
    return visibleDateKeys.has(ownDateKey) || (Number.isFinite(previousDateKey) && visibleDateKeys.has(previousDateKey));
  });

  function toggleChain(chain: string) {
    setSelectedChains((current) => {
      if (current.includes(chain) && current.length === 1) return current;
      if (current.includes(chain)) return current.filter((item) => item !== chain);
      return [...current, chain];
    });
  }

  function changePeriod(days: string) {
    if (days === activeHistoryDays) return;
    setActiveHistoryDays(days);
    startTransition(() => {
      router.replace(periodHref(productKey, context, days), { scroll: false });
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <Button asChild variant="outline" className="h-8">
          <Link href={source === "radar" ? "/pricing/intraday-radar" : "/pricing/executive-signals"}>
            <ArrowLeft className="h-4 w-4" />
            {source === "radar" ? "Price radar" : "Pricing"}
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
                  onClick={() => changePeriod(option.days)}
                >
                  {option.label}
                </Button>
              ))}
              {rangeLabel && (
                <span className="text-[10px] text-ink-muted">{rangeLabel}</span>
              )}
            </div>
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
            <ProductNormalPromoPriceCharts history={payload.price_history} selectedChains={displayedChains} priceMode={priceMode} />
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

      {activeTab === "position" ? <section className="space-y-3">
        <div className="flex items-center gap-2">
          <GitCompare className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-medium">Market Position</h2>
        </div>
        <Card>
          <CardHeader>
            <div className="font-medium">Chain-level price position</div>
            <div className="mt-1 text-sm text-muted-foreground">Latest available capture by chain for this product.</div>
          </CardHeader>
          <CardContent className="p-0">
            <IntradayProductChainGrid records={payload.chain_snapshot} />
          </CardContent>
        </Card>
      </section> : null}
    </div>
  );
}

export const ProductIntelligencePage = IntradayProductPage;
