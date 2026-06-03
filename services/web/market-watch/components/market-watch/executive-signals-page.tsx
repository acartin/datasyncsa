import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { FocusModeToggle } from "@/components/portal/focus-mode-toggle";
import { SignalFiltersForm } from "@/components/market-watch/signal-filters-form";
import { SignalGrid } from "@/components/market-watch/signal-grid";
import { SignalKpiCards } from "@/components/market-watch/signal-kpi-cards";
import { ExecutiveSignalSearchParams, ExecutiveSignalsPayload } from "@/lib/pricing-types";

function selectedCampaign(payload: ExecutiveSignalsPayload, values: ExecutiveSignalSearchParams) {
  if (values.campaign_id) {
    return payload.filters.campaigns.find((campaign) => campaign.id === values.campaign_id)?.label ?? values.campaign_id;
  }
  return payload.items[0]?.campaign ?? "All campaigns";
}

function selectedRange(payload: ExecutiveSignalsPayload, values: ExecutiveSignalSearchParams) {
  if (values.date_from || values.date_to) {
    return `${values.date_from || "Start"} -> ${values.date_to || "Today"}`;
  }
  return payload.kpis.latest_business_date ? `Latest date ${payload.kpis.latest_business_date}` : "Latest available";
}

function pageHref(filters: ExecutiveSignalSearchParams, offset: number, limit: number) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value && key !== "offset") params.set(key, value);
  });
  params.set("limit", String(limit));
  params.set("offset", String(Math.max(0, offset)));
  return `/pricing/executive-signals?${params.toString()}`;
}

export function ExecutiveSignalsPage({
  payload,
  filters
}: {
  payload: ExecutiveSignalsPayload;
  filters: ExecutiveSignalSearchParams;
}) {
  return (
    <div className="space-y-6">
      <div className="focus-hidden flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge>{selectedCampaign(payload, filters)}</Badge>
            <Badge>{selectedRange(payload, filters)}</Badge>
            {payload.kpis.latest_business_date ? <Badge>Updated {payload.kpis.latest_business_date}</Badge> : null}
          </div>
          <h1 className="text-2xl font-light">Executive Signals</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Prioritized commercial signals to decide what to review first and navigate directly to price, chain and evidence.
          </p>
        </div>
      </div>

      <div className="focus-hidden">
        <SignalKpiCards kpis={payload.kpis} />
      </div>
      <div className="focus-hidden">
        <SignalFiltersForm filters={payload.filters} values={filters} />
      </div>

      <Card className="focus-grid-card">
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <div className="font-medium">Prioritized signals</div>
            <div className="mt-1 text-sm text-muted-foreground">
              Sorted by date, impact and severity so the highest commercial pressure cases can be validated first.
            </div>
          </div>
          <FocusModeToggle />
        </CardHeader>
        <CardContent className="p-0">
          <SignalGrid signals={payload.items} />
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
            <div>
              {payload.offset + 1}-{Math.min(payload.offset + payload.items.length, payload.kpis.total_signals)} of {payload.kpis.total_signals}
            </div>
            <div className="flex gap-2">
              <Button asChild variant="outline" disabled={payload.offset <= 0}>
                <Link href={pageHref(filters, payload.offset - payload.limit, payload.limit)}>Prev</Link>
              </Button>
              <Button asChild variant="outline" disabled={payload.offset + payload.limit >= payload.kpis.total_signals}>
                <Link href={pageHref(filters, payload.offset + payload.limit, payload.limit)}>Next</Link>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
