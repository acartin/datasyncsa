"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { SignalSeverityBadge } from "@/components/market-watch/signal-severity-badge";
import { Button } from "@/components/ui/button";
import { IntradayRadarEvent } from "@/lib/pricing-types";

function currency(value: unknown) {
  if (typeof value !== "number") return "-";
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function percent(value: unknown) {
  if (typeof value !== "number") return "-";
  return `${value.toFixed(1)}%`;
}

function formatValue(record: IntradayRadarEvent, value: number | null) {
  if (record.event_area === "promotion") return percent(value);
  return currency(value);
}

const columns: DataGridColumn<IntradayRadarEvent>[] = [
  { id: "business_date", header: "Fecha", className: "whitespace-nowrap" },
  { id: "event_area", header: "Área", className: "whitespace-nowrap" },
  { id: "event_type", header: "Evento", className: "whitespace-nowrap" },
  {
    id: "severity",
    header: "Severidad",
    cell: (record) => <SignalSeverityBadge severity={record.severity} />
  },
  { id: "brand", header: "Marca", className: "whitespace-nowrap" },
  { id: "chain", header: "Cadena", className: "whitespace-nowrap" },
  {
    id: "product",
    header: "Producto",
    className: "min-w-80",
    cell: (record) =>
      record.product_key ? (
        <Link
          className="font-medium text-primary hover:underline"
          href={`/pricing/intraday-radar/products/${record.product_key}?campaign_id=${record.campaign_id}&date_key=${record.date_key}&chain=${encodeURIComponent(record.chain)}`}
        >
          {record.product}
        </Link>
      ) : (
        record.product
      )
  },
  {
    id: "previous_value",
    header: "Anterior",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => formatValue(record, record.previous_value),
    sortValue: (record) => record.previous_value
  },
  {
    id: "current_value",
    header: "Actual",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => formatValue(record, record.current_value),
    sortValue: (record) => record.current_value
  },
  {
    id: "change_pct",
    header: "Cambio",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => (record.event_area === "promotion" ? `${record.change_amount?.toFixed(1) ?? "-"} pts` : percent(record.change_pct)),
    sortValue: (record) => Math.abs(record.change_pct ?? record.change_amount ?? 0)
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

export function IntradayRadarGrid({ events }: { events: IntradayRadarEvent[] }) {
  return (
    <DataGrid
      columns={columns}
      records={events}
      className="max-h-[58vh] focus-grid-scroll"
      emptyTitle="Sin movimientos día contra día"
      emptyDescription="No hay cambios de precio u oferta para los filtros actuales."
    />
  );
}
