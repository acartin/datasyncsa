import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ProductVisual } from "@/components/market-watch/product-visual";
import { SignalSeverityBadge } from "@/components/market-watch/signal-severity-badge";
import { SignalStatusBadge } from "@/components/market-watch/signal-status-badge";
import { SkuPriceDriversGrid } from "@/components/market-watch/sku-price-drivers-grid";
import { StoreEvidenceGrid } from "@/components/market-watch/store-evidence-grid";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SignalDetailPayload, SkuPriceDriver, StoreEvidence } from "@/lib/pricing-types";

function DetailItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm">{value || "-"}</div>
    </div>
  );
}

function firstValue<T>(items: T[], getter: (item: T) => string | null | undefined) {
  return items.map(getter).find((value) => Boolean(value)) ?? null;
}

function textValue(value: unknown) {
  return value === null || value === undefined ? null : String(value);
}

function uniqueImages(drivers: SkuPriceDriver[], evidence: StoreEvidence[]) {
  const urls = [
    ...drivers.map((item) => item.image_url),
    ...drivers.map((item) => item.best_price_image_url),
    ...evidence.map((item) => item.image_url)
  ].filter((url): url is string => Boolean(url));
  return Array.from(new Set(urls)).slice(0, 4);
}

export function SignalDetailPage({ payload }: { payload: SignalDetailPayload }) {
  if (!payload.signal) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline">
          <Link href="/pricing/executive-signals">
            <ArrowLeft className="h-4 w-4" />
            Executive Signals
          </Link>
        </Button>
        <Card>
          <CardContent>
            <EmptyState
              title="Signal not found"
              description="The signal does not exist for the active client or is no longer published in the semantic layer."
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  const signal = payload.signal;
  const firstDriver = payload.drivers[0];
  const firstEvidence = payload.evidence[0];
  const hasSku = Boolean(signal.product_key);
  const images = uniqueImages(payload.drivers, payload.evidence);
  const product = textValue(firstDriver?.product) ?? textValue(firstEvidence?.product) ?? signal.evidence_product ?? signal.product_display;
  const gtin = firstValue(payload.drivers, (item) => textValue(item.gtin)) ?? firstValue(payload.evidence, (item) => textValue(item.gtin));
  const productKey = signal.product_key ?? textValue(firstDriver?.product_key) ?? textValue(firstEvidence?.product_key);
  const productUrl = firstValue(payload.drivers, (item) => item.product_url) ?? firstValue(payload.evidence, (item) => item.product_url);
  const hasSynthesis = Boolean(signal.summary || signal.business_reading || signal.recommended_action);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div className="w-full max-w-5xl">
          <Button asChild variant="outline" className="mb-4">
            <Link href="/pricing/executive-signals">
              <ArrowLeft className="h-4 w-4" />
              Executive Signals
            </Link>
          </Button>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <SignalSeverityBadge severity={signal.severity} />
            <SignalStatusBadge status={signal.signal_status} />
            <span className="text-sm text-muted-foreground">{signal.business_date}</span>
          </div>
          <h1 className="max-w-5xl text-2xl font-light">{signal.headline}</h1>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">{signal.summary}</p>
          {hasSynthesis ? (
            <div className="mt-4 overflow-hidden rounded-lg border border-border/70 bg-card/80 shadow-sm">
              <div className="border-b border-border/70 bg-muted/40 px-4 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">LLM Synthesis</div>
              </div>
              <div className="grid gap-4 px-4 py-4 md:grid-cols-2">
                <div className="space-y-3">
                  <div>
                    <div className="text-xs font-medium uppercase text-muted-foreground">Business Reading</div>
                    <p className="mt-1 text-sm leading-6 text-foreground/90">{signal.business_reading || "No business reading available."}</p>
                  </div>
                </div>
                <div className="space-y-3">
                  <div>
                    <div className="text-xs font-medium uppercase text-muted-foreground">Recommended Action</div>
                    <p className="mt-1 text-sm leading-6 text-foreground/90">{signal.recommended_action || "No recommended action available."}</p>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="font-medium">Signal Summary</div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-5 lg:flex-row">
            <ProductVisual hasSku={hasSku} images={images} />
            <div className="min-w-0 flex-1 space-y-5">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <DetailItem label="Campaign" value={signal.campaign} />
                <DetailItem label="Brand" value={signal.brand} />
                <DetailItem label="Chain" value={signal.chain} />
                <DetailItem label="Product" value={product} />
                <DetailItem label="GTIN" value={gtin} />
                <DetailItem label="Product key" value={productKey ?? (hasSku ? "-" : "Multiple products")} />
                <DetailItem label="Signal type" value={signal.signal_type} />
                <DetailItem label="Impact score" value={signal.impact_score} />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <DetailItem label="Business reading" value={signal.business_reading} />
                <DetailItem label="Recommended action" value={signal.recommended_action} />
                <DetailItem label="Repeat count" value={signal.repeat_count} />
                <DetailItem
                  label="Product URL"
                  value={
                    productUrl ? (
                      <a className="font-medium text-semantic-blue hover:underline" href={productUrl} target="_blank" rel="noreferrer">
                        Open product
                      </a>
                    ) : (
                      "-"
                    )
                  }
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="font-medium">SKU Price Drivers</div>
          <div className="mt-1 text-sm text-muted-foreground">Chain comparison to validate gap, index and suggested action.</div>
        </CardHeader>
        <CardContent>
          <SkuPriceDriversGrid drivers={payload.drivers} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="font-medium">Store Evidence</div>
          <div className="mt-1 text-sm text-muted-foreground">Store-level evidence with observed price, promotion and verifiable URL.</div>
        </CardHeader>
        <CardContent>
          <StoreEvidenceGrid evidence={payload.evidence} />
        </CardContent>
      </Card>
    </div>
  );
}
