"use client";

import { ExternalLink } from "lucide-react";
import { ChainTag } from "@/components/market-watch/chain-tag";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { SignalStatusBadge } from "@/components/market-watch/signal-status-badge";
import { Button } from "@/components/ui/button";
import { StoreEvidence } from "@/lib/pricing-types";

function currency(value: unknown) {
  if (typeof value !== "number") return "-";
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function percent(value: unknown) {
  if (typeof value !== "number") return "-";
  return `${value.toFixed(1)}%`;
}

const columns: DataGridColumn<StoreEvidence>[] = [
  { id: "chain", header: "Chain", className: "whitespace-nowrap", cell: (record) => <ChainTag chain={record.chain} /> },
  { id: "store", header: "Store", className: "min-w-48" },
  { id: "observed_price", header: "Observed price", className: "text-right", headerClassName: "text-right", cell: (record) => <span className="font-mono">{currency(record.observed_price)}</span>, sortValue: (record) => record.observed_price },
  { id: "captured_at_cr", header: "Captured", className: "whitespace-nowrap" },
  {
    id: "promo_detected",
    header: "Promo",
    cell: (record) => <SignalStatusBadge status={record.promo_detected ? "active" : "none"} />
  },
  { id: "discount_pct", header: "Discount", className: "text-right", headerClassName: "text-right", cell: (record) => <span className="font-mono">{percent(record.discount_pct)}</span>, sortValue: (record) => record.discount_pct },
  {
    id: "product_url",
    header: "URL",
    sortable: false,
    className: "text-right",
    cell: (record) =>
      record.product_url ? (
        <Button asChild variant="ghost" className="h-8 w-8 px-0" title="Open evidence">
          <a href={record.product_url} target="_blank" rel="noreferrer">
            <ExternalLink className="h-4 w-4" />
          </a>
        </Button>
      ) : (
        "-"
      )
  }
];

export function StoreEvidenceGrid({ evidence }: { evidence: StoreEvidence[] }) {
  return (
    <DataGrid
      columns={columns}
      records={evidence}
      emptyTitle="No store evidence"
      emptyDescription="No evidence has been published for this date, campaign and product combination."
    />
  );
}
