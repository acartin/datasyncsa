"use client";

import { ExternalLink } from "lucide-react";
import { ChainTag } from "@/components/market-watch/chain-tag";
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
  { id: "chain", header: "Chain", className: "whitespace-nowrap", cell: (record) => <ChainTag chain={record.chain} /> },
  { id: "average_price", header: "Avg price", className: "text-right", headerClassName: "text-right", cell: (record) => <span className="font-mono">{currency(record.average_price)}</span>, sortValue: (record) => record.average_price },
  { id: "best_chain_average_price", header: "Best avg", className: "text-right", headerClassName: "text-right", cell: (record) => <span className="font-mono">{currency(record.best_chain_average_price)}</span>, sortValue: (record) => record.best_chain_average_price },
  { id: "best_chain", header: "Best chain", className: "whitespace-nowrap", cell: (record) => <ChainTag chain={record.best_chain} /> },
  { id: "gap_pct", header: "Gap", className: "text-right", headerClassName: "text-right", cell: (record) => <span className="font-mono font-medium text-semantic-amber">{percent(record.gap_pct)}</span>, sortValue: (record) => record.gap_pct },
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

export function SkuPriceDriversGrid({ drivers }: { drivers: SkuPriceDriver[] }) {
  return (
    <DataGrid
      columns={columns}
      records={drivers}
      emptyTitle="No drivers for this signal"
      emptyDescription="The signal has no specific SKU or no drivers have been published in the semantic layer yet."
    />
  );
}
