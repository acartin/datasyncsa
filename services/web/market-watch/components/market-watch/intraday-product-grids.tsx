"use client";

import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, ExternalLink, Minus } from "lucide-react";
import { ChainTag } from "@/components/market-watch/chain-tag";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { Button } from "@/components/ui/button";
import { changeIndicator, changeToneClass, formatEventChangeValue, formatEventValue, showChangeValue } from "@/lib/event-presentation";
import { IntradayProductChainSnapshot, IntradayProductStoreEvidence, IntradayRadarEvent } from "@/lib/pricing-types";

function compactDateKey(value: unknown) {
  const text = String(value ?? "");
  if (!/^\d{8}$/.test(text)) return text || "-";
  return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
}

function percent(value: unknown) {
  if (typeof value !== "number") return "-";
  return `${value.toFixed(1)}%`;
}

function currency(value: unknown) {
  if (typeof value !== "number") return "-";
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function numberValue(value: unknown) {
  if (typeof value !== "number") return "-";
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, "");
}

function status(value: unknown, activeLabel: string, inactiveLabel: string) {
  if (typeof value !== "boolean") return "-";
  return value ? activeLabel : inactiveLabel;
}

function ChangeIndicatorIcon({ record }: { record: IntradayRadarEvent }) {
  const indicator = changeIndicator(record);
  if (indicator === "up") return <ArrowUpRight className="h-3.5 w-3.5" />;
  if (indicator === "down") return <ArrowDownRight className="h-3.5 w-3.5" />;
  if (indicator === "flat") return <Minus className="h-3.5 w-3.5" />;
  return null;
}

const chainColumns: DataGridColumn<IntradayProductChainSnapshot>[] = [
  { id: "chain", header: "Chain", className: "whitespace-nowrap", cell: (record) => <ChainTag chain={record.chain} /> },
  { id: "captured_at_cr", header: "Last capture", className: "whitespace-nowrap" },
  {
    id: "average_price",
    header: "Avg price",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{currency(record.average_price)}</span>,
    sortValue: (record) => record.average_price
  },
  {
    id: "average_unit_price",
    header: "Unit price",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{currency(record.average_unit_price)}</span>,
    sortValue: (record) => record.average_unit_price
  },
  {
    id: "promo_detected",
    header: "Promo",
    cell: (record) => (record.promo_detected ? "Active" : "None")
  },
  {
    id: "max_discount_pct",
    header: "Discount",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{percent(record.max_discount_pct)}</span>,
    sortValue: (record) => record.max_discount_pct
  },
  {
    id: "visible_locations",
    header: "Visible",
    className: "text-right",
    headerClassName: "text-right"
  },
  {
    id: "available_locations",
    header: "Available",
    className: "text-right",
    headerClassName: "text-right"
  },
  {
    id: "product_url",
    header: "URL",
    sortable: false,
    className: "text-right",
    cell: (record) =>
      record.product_url ? (
        <Button asChild variant="ghost" className="h-8 w-8 px-0" title="Open product">
          <a href={record.product_url} target="_blank" rel="noreferrer">
            <ExternalLink className="h-4 w-4" />
          </a>
        </Button>
      ) : (
        "-"
      )
  }
];

const eventColumns: DataGridColumn<IntradayRadarEvent>[] = [
  {
    id: "business_date",
    header: "Date",
    className: "whitespace-nowrap",
    cell: (record) => {
      const previousDateKey = record.previous_date_key;
      if (previousDateKey && Number(previousDateKey) !== Number(record.date_key)) {
        return (
          <div className="leading-tight">
            <div>{String(record.business_date)}</div>
            <div className="text-[10px] text-ink-muted">{compactDateKey(previousDateKey)} {"->"} {compactDateKey(record.date_key)}</div>
          </div>
        );
      }
      return String(record.business_date);
    }
  },
  { id: "event_area", header: "Area", className: "whitespace-nowrap" },
  {
    id: "event_type",
    header: "Event",
    className: "whitespace-nowrap",
    cell: (record) => record.presentation?.short_label ?? record.event_type
  },
  { id: "chain", header: "Chain", className: "whitespace-nowrap", cell: (record) => <ChainTag chain={record.chain} /> },
  {
    id: "previous_value",
    header: "Previous",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{formatEventValue(record, record.previous_value, "previous")}</span>
  },
  {
    id: "current_value",
    header: "Current",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{formatEventValue(record, record.current_value, "current")}</span>
  },
  {
    id: "change_pct",
    header: "Change",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => {
      if (!showChangeValue(record)) return <span className="font-mono text-ink-muted">-</span>;
      return (
        <span className={`inline-flex items-center gap-1 font-mono font-medium ${changeToneClass(record)}`}>
          <ChangeIndicatorIcon record={record} />
          {formatEventChangeValue(record)}
        </span>
      );
    }
  }
];

const storeColumns: DataGridColumn<IntradayProductStoreEvidence>[] = [
  { id: "chain", header: "Chain", className: "whitespace-nowrap", cell: (record) => <ChainTag chain={record.chain} /> },
  { id: "location_name", header: "Store", className: "min-w-56" },
  {
    id: "location",
    header: "Location",
    className: "min-w-56",
    cell: (record) => [record.province, record.canton, record.district].filter(Boolean).join(" / ") || "-"
  },
  { id: "captured_at_cr", header: "Last capture", className: "whitespace-nowrap" },
  {
    id: "is_listed",
    header: "Listed",
    cell: (record) => status(record.is_listed, "Yes", "No")
  },
  {
    id: "is_available",
    header: "Available",
    cell: (record) => status(record.is_available, "Yes", "No")
  },
  {
    id: "available_quantity",
    header: "Source qty",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{numberValue(record.available_quantity)}</span>,
    sortValue: (record) => record.available_quantity
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
    id: "spot_price_amount",
    header: "Promo",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{currency(record.spot_price_amount)}</span>,
    sortValue: (record) => record.spot_price_amount
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

export function IntradayProductChainGrid({ records }: { records: IntradayProductChainSnapshot[] }) {
  return (
    <DataGrid
      columns={chainColumns}
      records={records}
      emptyTitle="No chain prices"
      emptyDescription="No consolidated chain captures are available for this product."
    />
  );
}

function storeDetailHref(record: IntradayProductStoreEvidence, context?: StoreEvidenceNavigationContext) {
  if (!context?.productKey || !record.location_key) return null;
  const search = new URLSearchParams();
  if (context.campaignId) search.set("campaign_id", context.campaignId);
  if (context.dateKey) search.set("date_key", context.dateKey);
  if (context.chain ?? record.chain) search.set("chain", context.chain ?? record.chain);
  if (context.historyDays) search.set("history_days", context.historyDays);
  search.set("source", "store-evidence");
  return `/pricing/intraday-radar/products/${encodeURIComponent(context.productKey)}/stores/${encodeURIComponent(String(record.location_key))}?${search.toString()}`;
}

type StoreEvidenceNavigationContext = {
  productKey?: string | null;
  campaignId?: string;
  dateKey?: string;
  chain?: string;
  historyDays?: string;
};

export function IntradayProductStoreEvidenceGrid({
  records,
  navigationContext,
}: {
  records: IntradayProductStoreEvidence[];
  navigationContext?: StoreEvidenceNavigationContext;
}) {
  const columns = storeColumns.map((column) => {
    if (column.id !== "location_name") return column;
    return {
      ...column,
      cell: (record: IntradayProductStoreEvidence) => {
        const href = storeDetailHref(record, navigationContext);
        const label = record.location_name ?? "-";
        if (!href) return label;
        return (
          <Link
            href={href}
            className="inline-flex items-center whitespace-nowrap rounded-[6px] border border-border-2 bg-card px-2 py-1 text-xs font-medium text-foreground transition-colors hover:border-foreground hover:bg-surface-2"
          >
            {label}
          </Link>
        );
      }
    };
  });

  return (
    <DataGrid
      columns={columns}
      records={records}
      emptyTitle="No store evidence"
      emptyDescription="No store-level captures are available for this product and chain."
    />
  );
}

export function IntradayProductEventsGrid({ records }: { records: IntradayRadarEvent[] }) {
  return (
    <DataGrid
      columns={eventColumns}
      records={records}
      emptyTitle="No related events"
      emptyDescription="No day-over-day movements are associated with this product."
    />
  );
}
