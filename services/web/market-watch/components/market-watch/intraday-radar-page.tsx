import Link from "next/link";
import { Activity, AlertTriangle, Bell, Percent } from "lucide-react";
import { FocusModeToggle } from "@/components/portal/focus-mode-toggle";
import { IntradayRadarFiltersForm } from "@/components/market-watch/intraday-radar-filters-form";
import { IntradayRadarGrid } from "@/components/market-watch/intraday-radar-grid";
import { KpiCard } from "@/components/market-watch/kpi-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { IntradayRadarPayload, IntradayRadarSearchParams } from "@/lib/pricing-types";

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
    return payload.filters.campaigns.find((campaign) => campaign.id === values.campaign_id)?.label ?? values.campaign_id;
  }
  return payload.items[0]?.campaign ?? "All campaigns";
}

function displayDateKey(value?: number | null) {
  if (!value) return "No date";
  const raw = String(value);
  if (raw.length !== 8) return raw;
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

export function IntradayRadarPage({
  payload,
  filters
}: {
  payload: IntradayRadarPayload;
  filters: IntradayRadarSearchParams;
}) {
  return (
    <div className="space-y-6">
      <div className="focus-hidden flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge>{selectedCampaign(payload, filters)}</Badge>
            <Badge>Día cerrado {displayDateKey(payload.kpis.selected_date_key ?? payload.kpis.latest_date_key)}</Badge>
            {payload.kpis.prior_closed_date_key ? <Badge>Base DoD {displayDateKey(payload.kpis.prior_closed_date_key)}</Badge> : null}
            {payload.kpis.latest_capture ? <Badge>Última captura {payload.kpis.latest_capture}</Badge> : null}
          </div>
          <h1 className="text-2xl font-semibold">Radar de precios y ofertas</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Cambios día contra día del último día cerrado contra el día anterior, agregados por producto y cadena.
          </p>
        </div>
      </div>

      <div className="focus-hidden grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard icon={Activity} value={payload.kpis.total_events ?? 0} label="Eventos" />
        <KpiCard icon={Bell} value={payload.kpis.price_events ?? 0} label="Cambios de precio" />
        <KpiCard icon={Percent} value={payload.kpis.promo_events ?? 0} label="Cambios de oferta" />
        <KpiCard icon={AlertTriangle} value={payload.kpis.high_severity_events ?? 0} label="Alta severidad" />
      </div>

      <div className="focus-hidden">
        <IntradayRadarFiltersForm filters={payload.filters} values={filters} />
      </div>

      <Card className="focus-grid-card">
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <div className="font-medium">Movimientos día contra día</div>
            <div className="mt-1 text-sm text-muted-foreground">
              Comparan precio normal, precio promocional y estado de oferta entre dos días cerrados consecutivos.
            </div>
          </div>
          <FocusModeToggle />
        </CardHeader>
        <CardContent className="p-0">
          <IntradayRadarGrid events={payload.items} />
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
            <div>
              {payload.items.length ? payload.offset + 1 : 0}-{Math.min(payload.offset + payload.items.length, payload.kpis.total_events)} de{" "}
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
