"use client";

import { ExternalLink } from "lucide-react";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { SignalSeverityBadge } from "@/components/market-watch/signal-severity-badge";
import { Button } from "@/components/ui/button";
import { IntradayProductChainSnapshot, IntradayRadarEvent } from "@/lib/pricing-types";

function currency(value: unknown) {
  if (typeof value !== "number") return "-";
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function percent(value: unknown) {
  if (typeof value !== "number") return "-";
  return `${value.toFixed(1)}%`;
}

function valueForEvent(record: IntradayRadarEvent, value: number | null) {
  return record.event_area === "promotion" ? percent(value) : currency(value);
}

const chainColumns: DataGridColumn<IntradayProductChainSnapshot>[] = [
  { id: "chain", header: "Chain", className: "whitespace-nowrap" },
  { id: "captured_at_cr", header: "Last capture", className: "whitespace-nowrap" },
  {
    id: "average_price",
    header: "Avg price",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => currency(record.average_price),
    sortValue: (record) => record.average_price
  },
  {
    id: "average_unit_price",
    header: "Unit price",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => currency(record.average_unit_price),
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
    cell: (record) => percent(record.max_discount_pct),
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
        <Button asChild variant="ghost" className="h-8 w-8 px-0" title="Abrir producto">
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
  { id: "business_date", header: "Date", className: "whitespace-nowrap" },
  { id: "event_area", header: "Area", className: "whitespace-nowrap" },
  { id: "event_type", header: "Event", className: "whitespace-nowrap" },
  { id: "chain", header: "Chain", className: "whitespace-nowrap" },
  {
    id: "severity",
    header: "Severity",
    cell: (record) => <SignalSeverityBadge severity={record.severity} />
  },
  {
    id: "previous_value",
    header: "Previous",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => valueForEvent(record, record.previous_value)
  },
  {
    id: "current_value",
    header: "Current",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => valueForEvent(record, record.current_value)
  },
  {
    id: "change_pct",
    header: "Change",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => (record.event_area === "promotion" ? `${record.change_amount?.toFixed(1) ?? "-"} pts` : percent(record.change_pct))
  }
];

export function IntradayProductChainGrid({ records }: { records: IntradayProductChainSnapshot[] }) {
  return (
    <DataGrid
      columns={chainColumns}
      records={records}
      emptyTitle="Sin precio por cadena"
      emptyDescription="No hay capturas consolidadas por cadena para este producto."
    />
  );
}

export function IntradayProductEventsGrid({ records }: { records: IntradayRadarEvent[] }) {
  return (
    <DataGrid
      columns={eventColumns}
      records={records}
      emptyTitle="Sin eventos relacionados"
      emptyDescription="No hay movimientos día contra día asociados a este producto."
    />
  );
}
