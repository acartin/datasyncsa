import Link from "next/link";
import { Activity, AlertTriangle, Bell, Percent } from "lucide-react";
import { FocusModeToggle } from "@/components/portal/focus-mode-toggle";
import { DataViewToolbar, DataViewFilterConfig } from "@/components/market-watch/data-view-toolbar";
import { IntradayRadarGrid } from "@/components/market-watch/intraday-radar-grid";
import { KpiCard } from "@/components/market-watch/kpi-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { costaRicaYesterdayInputValue } from "@/lib/closed-day";
import { IntradayRadarPayload, IntradayRadarSearchParams } from "@/lib/pricing-types";
import { DataViewState, SavedTableView } from "@/lib/data-views";

function pageHref(filters: IntradayRadarSearchParams, offset: number, limit: number) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value && key !== "offset") params.set(key, value);
  });
  params.set("limit", String(limit));
  params.set("offset", String(Math.max(0, offset)));
  return `/pricing/intraday-radar?${params.toString()}`;
}

function selectedCampaign(payload: IntradayRadarPayload, values: IntradayRadarSearchParams) {
  if (values.campaign_id) {
    const selected = splitValues(values.campaign_id);
    if (selected.length > 1) return `${selected.length} campaigns`;
    return payload.filters.campaigns.find((campaign) => campaign.id === selected[0])?.label ?? selected[0];
  }
  return payload.items[0]?.campaign ?? "All campaigns";
}

function displayDateKey(value?: number | null) {
  if (!value) return "No date";
  const raw = String(value);
  if (raw.length !== 8) return raw;
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

function splitValues(value?: string) {
  return value ? value.split(",").filter(Boolean) : [];
}

function currentViewState(filters: IntradayRadarSearchParams): DataViewState {
  return {
    search: filters.q,
    filters: {
      campaign_id: splitValues(filters.campaign_id),
      brand: splitValues(filters.brand),
      chain: splitValues(filters.chain),
      product_key: splitValues(filters.product_key),
    },
    dates: filters.date_key
      ? { date_key: { mode: "single", value: filters.date_key } }
      : filters.date_key_preset
        ? { date_key: { mode: "relative", preset: filters.date_key_preset } }
        : filters.date_key_from || filters.date_key_to
          ? { date_key: { mode: "range", from: filters.date_key_from, to: filters.date_key_to } }
          : undefined,
  };
}

function toolbarFilters(payload: IntradayRadarPayload): DataViewFilterConfig[] {
  return [
    { key: "campaign_id", label: "Campaign", type: "multiselect", options: payload.filters.campaigns, searchable: true },
    { key: "product_key", label: "Product", type: "product", options: payload.filters.products, searchable: true },
    { key: "brand", label: "Brand", type: "multiselect", options: payload.filters.brands, searchable: true },
    { key: "chain", label: "Chain", type: "multiselect", options: payload.filters.chains, searchable: true },
  ];
}

export function IntradayRadarPage({
  payload,
  filters,
  tableViews,
  viewKey
}: {
  payload: IntradayRadarPayload;
  filters: IntradayRadarSearchParams;
  tableViews: SavedTableView[];
  viewKey: string;
}) {
  const viewState = currentViewState(filters);

  return (
    <div className="space-y-5">
      <div className="focus-hidden flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge>{selectedCampaign(payload, filters)}</Badge>
            <Badge>Closed day {displayDateKey(payload.kpis.selected_date_key ?? payload.kpis.latest_date_key)}</Badge>
            {payload.kpis.prior_closed_date_key ? <Badge>Base DoD {displayDateKey(payload.kpis.prior_closed_date_key)}</Badge> : null}
            {payload.kpis.latest_capture ? <Badge>Latest capture {payload.kpis.latest_capture}</Badge> : null}
          </div>
          <h1 className="text-[22px] font-light leading-tight tracking-[-0.01em]">Price and promotion radar</h1>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-ink-muted">
            Day-over-day changes for the latest closed day compared with the previous day, grouped by product and chain.
          </p>
        </div>
      </div>

      <div className="focus-hidden grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard icon={Activity} value={payload.kpis.total_events ?? 0} label="Events" variant="blue" />
        <KpiCard icon={Bell} value={payload.kpis.price_events ?? 0} label="Price changes" variant="amber" />
        <KpiCard icon={Percent} value={payload.kpis.promo_events ?? 0} label="Promotion changes" variant="green" />
        <KpiCard icon={AlertTriangle} value={payload.kpis.high_severity_events ?? 0} label="High severity" variant="red" />
      </div>

      <div className="focus-hidden">
        <DataViewToolbar
          basePath="/pricing/intraday-radar"
          viewKey={viewKey}
          title="Day-over-day movements"
          currentState={viewState}
          views={tableViews}
          filters={toolbarFilters(payload)}
          dateFilters={[{ key: "date_key", label: "Closed day", max: costaRicaYesterdayInputValue() }]}
        />
      </div>

      <Card className="focus-grid-card">
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <div className="text-[13px] font-medium">Day-over-day movements</div>
            <div className="mt-1 text-[11px] text-ink-muted">
              Compares regular price, promotional price and promotion status across consecutive closed days.
            </div>
          </div>
          <FocusModeToggle />
        </CardHeader>
        <CardContent className="p-0">
          <IntradayRadarGrid events={payload.items} />
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
            <div>
              {payload.items.length ? payload.offset + 1 : 0}-{Math.min(payload.offset + payload.items.length, payload.kpis.total_events)} of{" "}
              {payload.kpis.total_events}
            </div>
            <div className="flex gap-2">
              <Button asChild variant="outline" disabled={payload.offset <= 0}>
                <Link href={pageHref(filters, payload.offset - payload.limit, payload.limit)}>Prev</Link>
              </Button>
              <Button asChild variant="outline" disabled={payload.offset + payload.limit >= payload.kpis.total_events}>
                <Link href={pageHref(filters, payload.offset + payload.limit, payload.limit)}>Next</Link>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
