"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { ChainTag } from "@/components/market-watch/chain-tag";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { ProductNormalPromoPriceCharts } from "@/components/market-watch/product-history-chart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { IntradayProductStoreCapture, IntradayProductStoreDetailPayload } from "@/lib/pricing-types";

const periodOptions = [
  { label: "7 days", days: "7" },
  { label: "30 days", days: "30" },
  { label: "90 days", days: "90" },
];

function currency(value: unknown) {
  if (typeof value !== "number") return "-";
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function percent(value: unknown) {
  if (typeof value !== "number") return "-";
  return `${value.toFixed(1)}%`;
}

function status(value: unknown) {
  if (typeof value !== "boolean") return "-";
  return value ? "Yes" : "No";
}

function productDetailHref(productKey: string, context: ProductStoreContext) {
  const search = new URLSearchParams();
  if (context.campaignId) search.set("campaign_id", context.campaignId);
  if (context.dateKey) search.set("date_key", context.dateKey);
  if (context.chain) search.set("chain", context.chain);
  search.set("source", "store-detail");
  return `/pricing/intraday-radar/products/${encodeURIComponent(productKey)}?${search.toString()}`;
}

function storeHref(productKey: string, locationKey: number | string, context: ProductStoreContext, days = context.historyDays ?? "30") {
  const search = new URLSearchParams();
  if (context.campaignId) search.set("campaign_id", context.campaignId);
  if (context.dateKey) search.set("date_key", context.dateKey);
  if (context.chain) search.set("chain", context.chain);
  search.set("history_days", days);
  search.set("source", "store-evidence");
  return `/pricing/intraday-radar/products/${encodeURIComponent(productKey)}/stores/${encodeURIComponent(String(locationKey))}?${search.toString()}`;
}

const captureColumns: DataGridColumn<IntradayProductStoreCapture>[] = [
  { id: "business_date", header: "Date", className: "whitespace-nowrap" },
  { id: "captured_at_cr", header: "Last capture", className: "whitespace-nowrap" },
  {
    id: "is_listed",
    header: "Listed",
    cell: (record) => status(record.is_listed)
  },
  {
    id: "is_available",
    header: "Available",
    cell: (record) => status(record.is_available)
  },
  {
    id: "reference_price_amount",
    header: "Regular",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{currency(record.reference_price_amount)}</span>,
    sortValue: (record) => record.reference_price_amount
  },
  {
    id: "promo_price_amount",
    header: "Promo",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{currency(record.promo_price_amount)}</span>,
    sortValue: (record) => record.promo_price_amount
  },
  {
    id: "effective_price_amount",
    header: "Effective",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{currency(record.effective_price_amount)}</span>,
    sortValue: (record) => record.effective_price_amount
  },
  {
    id: "discount_pct",
    header: "Discount",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{percent(record.discount_pct)}</span>,
    sortValue: (record) => record.discount_pct
  },
  {
    id: "product_url",
    header: "Live",
    sortable: false,
    className: "text-right",
    cell: (record) => {
      const href = typeof record.product_url === "string" && record.product_url ? record.product_url : null;
      return href ? (
        <Button
          asChild
          variant="ghost"
          className="h-8 w-8 px-0"
          title="Open live chain site. Price may differ by the store selected in your browser."
        >
          <a href={href} target="_blank" rel="noreferrer">
            <ExternalLink className="h-4 w-4" />
          </a>
        </Button>
      ) : (
        "-"
      );
    }
  }
];

export type ProductStoreContext = {
  campaignId?: string;
  dateKey?: string;
  chain?: string;
  historyDays?: string;
};

export function IntradayProductStorePage({
  payload,
  productKey,
  locationKey,
  context,
}: {
  payload: IntradayProductStoreDetailPayload;
  productKey: string;
  locationKey: string;
  context: ProductStoreContext;
}) {
  const router = useRouter();
  const product = payload.product;
  const selectedStore = payload.selected_store;
  const activeDays = context.historyDays ?? "30";

  if (!product || !selectedStore) {
    return <EmptyState title="Store history not found" description="No store-level captures are available for this product and store." />;
  }

  const productHref = productDetailHref(productKey, context);
  const currentPrice = product.current_effective_price ?? product.current_regular_price;

  return (
    <div className="space-y-4">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Button asChild variant="outline" className="h-8">
            <Link href={productHref}>
              <ArrowLeft className="h-4 w-4" />
              Product evidence
            </Link>
          </Button>
          <span className="text-border-2">/</span>
          <span>{selectedStore.location_name}</span>
          <span className="text-border-2">/</span>
          <span className="font-medium text-foreground">{product.product}</span>
        </div>
        <Card>
          <CardContent className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] text-ink-muted">
                <ChainTag chain={product.chain} />
                <span>{selectedStore.location_name}</span>
                <span className="text-border-2">/</span>
                <span>{product.brand}</span>
                <span className="text-border-2">/</span>
                <span>
                  {product.content_quantity ?? "-"} {product.content_unit ?? ""}
                </span>
                <span className="text-border-2">/</span>
                <span>Campaign {product.campaign_id}</span>
              </div>
              <h1 className="max-w-5xl text-xl font-light leading-snug">{product.product}</h1>
            </div>
            <div className="grid min-w-72 overflow-hidden rounded-lg border border-border-2 text-center text-sm sm:grid-cols-2">
              <div className="border-b border-border p-4 sm:border-b-0 sm:border-r">
                <div className="mb-1 text-[10px] uppercase tracking-[0.07em] text-ink-muted">Current</div>
                <div className="font-mono text-lg font-normal">{currency(currentPrice)}</div>
              </div>
              <div className="p-4">
                <div className="mb-1 text-[10px] uppercase tracking-[0.07em] text-ink-muted">Last capture</div>
                <div className="font-mono text-lg font-normal">{product.latest_capture ?? "-"}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div>
            <div className="text-[13px] font-medium">Store price timeline</div>
            <div className="mt-1 text-[11px] text-ink-muted">Price captures for this product in the selected store.</div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <div className="mr-1 w-12 text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Store</div>
            <select
              value={locationKey}
              className="h-8 min-w-56 rounded-[6px] border border-border-2 bg-card px-3 text-xs text-foreground"
              onChange={(event) => router.push(storeHref(productKey, event.target.value, context))}
            >
              {payload.store_options.map((store) => (
                <option key={store.location_key} value={store.location_key}>
                  {store.location_name}
                </option>
              ))}
            </select>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <div className="mr-1 w-12 text-[10px] font-medium uppercase tracking-[0.07em] text-ink-muted">Period</div>
            {periodOptions.map((option) => (
              <Button key={option.days} asChild variant="chip" data-active={activeDays === option.days}>
                <Link href={storeHref(productKey, selectedStore.location_key, context, option.days)}>{option.label}</Link>
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          <ProductNormalPromoPriceCharts history={payload.price_history} selectedChains={[product.chain]} priceMode="both" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-[13px] font-medium">Store captures</div>
          <div className="mt-1 text-[11px] text-ink-muted">Closed-day captures for this product and store.</div>
        </CardHeader>
        <CardContent className="p-0">
          <DataGrid columns={captureColumns} records={payload.captures} emptyTitle="No captures" emptyDescription="No captures are available for this period." />
        </CardContent>
      </Card>
    </div>
  );
}
