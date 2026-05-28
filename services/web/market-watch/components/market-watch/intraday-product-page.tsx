import Link from "next/link";
import { ArrowLeft, Percent, Store, Tags, Timer } from "lucide-react";
import { IntradayProductChainGrid, IntradayProductEventsGrid } from "@/components/market-watch/intraday-product-grids";
import { ProductNormalPromoPriceCharts } from "@/components/market-watch/product-history-chart";
import { KpiCard } from "@/components/market-watch/kpi-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { IntradayProductDetailPayload } from "@/lib/pricing-types";

function currency(value: unknown) {
  if (typeof value !== "number") return "-";
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function percent(value: unknown) {
  if (typeof value !== "number") return "-";
  return `${value.toFixed(1)}%`;
}

export function IntradayProductPage({ payload }: { payload: IntradayProductDetailPayload }) {
  const product = payload.product;
  if (!product) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline">
          <Link href="/pricing/intraday-radar">
            <ArrowLeft className="h-4 w-4" />
            Radar de precios y ofertas
          </Link>
        </Button>
        <Card>
          <CardContent>
            <EmptyState title="Producto no encontrado" description="No hay datos diarios consolidados para este producto." />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Button asChild variant="outline">
        <Link href="/pricing/intraday-radar">
          <ArrowLeft className="h-4 w-4" />
          Radar de precios y ofertas
        </Link>
      </Button>

      <Card>
        <CardContent className="flex flex-col gap-5 p-5 lg:flex-row">
          <div className="flex h-44 w-44 shrink-0 items-center justify-center overflow-hidden rounded-md border bg-background">
            {product.image_url ? <img src={product.image_url} alt={product.product} className="h-full w-full object-contain" /> : null}
          </div>
          <div className="min-w-0 flex-1">
            <div className="mb-2 text-sm font-medium uppercase text-muted-foreground">{product.brand}</div>
            <h1 className="text-2xl font-semibold">{product.product}</h1>
            <div className="mt-3 grid gap-3 text-sm md:grid-cols-4">
              <div>
                <div className="text-xs font-medium uppercase text-muted-foreground">GTIN</div>
                <div>{product.gtin ?? "-"}</div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase text-muted-foreground">Contenido</div>
                <div>
                  {product.content_quantity ?? "-"} {product.content_unit ?? ""}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase text-muted-foreground">Día cerrado</div>
                <div>{product.date_key}</div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase text-muted-foreground">Cadena</div>
                <div>{product.chain ?? "-"}</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard icon={Tags} label="Precio venta prom." value={currency(product.avg_price)} />
        <KpiCard icon={Store} label="Min / max" value={`${currency(product.min_price)} / ${currency(product.max_price)}`} />
        <KpiCard icon={Percent} label="Descuento max." value={percent(product.max_discount_pct)} />
        <KpiCard icon={Timer} label="Eventos DoD" value={payload.events.length} />
      </div>

      <Card>
        <CardHeader>
          <div className="font-medium">Últimas 30 mediciones de precio</div>
          <div className="mt-1 text-sm text-muted-foreground">SKU y cadena seleccionados. Precio normal contra precio promocional observado.</div>
        </CardHeader>
        <CardContent>
          <ProductNormalPromoPriceCharts history={payload.price_history} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="font-medium">Precio por cadena</div>
          <div className="mt-1 text-sm text-muted-foreground">Ultima captura disponible por cadena para este producto.</div>
        </CardHeader>
        <CardContent className="p-0">
          <IntradayProductChainGrid records={payload.chain_snapshot} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="font-medium">Eventos relacionados</div>
          <div className="mt-1 text-sm text-muted-foreground">Movimientos día contra día detectados para este SKU y cadena.</div>
        </CardHeader>
        <CardContent className="p-0">
          <IntradayProductEventsGrid records={payload.events} />
        </CardContent>
      </Card>
    </div>
  );
}
