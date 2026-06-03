"use client";

import { ArrowDownRight, ArrowUpRight, ExternalLink, Minus } from "lucide-react";
import { ChainTag } from "@/components/market-watch/chain-tag";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { Button } from "@/components/ui/button";
import { changeIndicator, changeToneClass, formatEventValue, showChangeValue } from "@/lib/event-presentation";
import { IntradayProductChainSnapshot, IntradayRadarEvent } from "@/lib/pricing-types";

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
      const value = record.event_area === "promotion" ? `${record.change_amount?.toFixed(1) ?? "-"} pts` : percent(record.change_pct);
      return (
        <span className={`inline-flex items-center gap-1 font-mono font-medium ${changeToneClass(record)}`}>
          <ChangeIndicatorIcon record={record} />
          {value}
        </span>
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
