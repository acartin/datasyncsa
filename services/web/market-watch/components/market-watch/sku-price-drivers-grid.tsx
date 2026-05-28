"use client";

import { ExternalLink } from "lucide-react";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { Button } from "@/components/ui/button";
import { SkuPriceDriver } from "@/lib/pricing-types";

function currency(value: unknown) {
  if (typeof value !== "number") return "-";
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function percent(value: unknown) {
  if (typeof value !== "number") return "-";
  return `${value.toFixed(1)}%`;
}

const columns: DataGridColumn<SkuPriceDriver>[] = [
  { id: "chain", header: "Chain", className: "whitespace-nowrap" },
  { id: "average_price", header: "Avg price", className: "text-right", headerClassName: "text-right", cell: (record) => currency(record.average_price), sortValue: (record) => record.average_price },
  { id: "best_chain_average_price", header: "Best avg", className: "text-right", headerClassName: "text-right", cell: (record) => currency(record.best_chain_average_price), sortValue: (record) => record.best_chain_average_price },
  { id: "best_chain", header: "Best chain", className: "whitespace-nowrap" },
  { id: "gap_pct", header: "Gap", className: "text-right", headerClassName: "text-right", cell: (record) => percent(record.gap_pct), sortValue: (record) => record.gap_pct },
  { id: "price_index", header: "Index", className: "text-right", headerClassName: "text-right" },
  { id: "price_reading", header: "Reading", className: "min-w-64" },
  { id: "suggested_action", header: "Suggested action", className: "min-w-64" },
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

export function SkuPriceDriversGrid({ drivers }: { drivers: SkuPriceDriver[] }) {
  return (
    <DataGrid
      columns={columns}
      records={drivers}
      emptyTitle="Sin drivers para esta senal"
      emptyDescription="La senal no tiene SKU puntual o aun no hay drivers publicados en la capa semantica."
    />
  );
}
