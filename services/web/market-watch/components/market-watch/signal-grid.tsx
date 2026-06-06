"use client";

import Link from "next/link";
import { ChainTag } from "@/components/market-watch/chain-tag";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { SignalStatusBadge } from "@/components/market-watch/signal-status-badge";
import { ExecutiveSignal } from "@/lib/pricing-types";

function formatScore(value: unknown) {
  if (typeof value !== "number") return "-";
  return value.toFixed(1);
}

function canonicalProductHref(record: ExecutiveSignal) {
  const search = new URLSearchParams({
    source: "signals",
  });
  if (record.campaign_id) search.set("campaign_id", String(record.campaign_id));
  return `/pricing/products/${record.product_key}?${search.toString()}`;
}

const columns: DataGridColumn<ExecutiveSignal>[] = [
  { id: "business_date", header: "Date", className: "whitespace-nowrap" },
  { id: "signal_type", header: "Type", className: "whitespace-nowrap" },
  { id: "brand", header: "Brand", className: "whitespace-nowrap" },
  {
    id: "chain",
    header: "Chain",
    className: "whitespace-nowrap",
    cell: (record) =>
      record.signal_id ? (
        <Link href={`/pricing/signals/${record.signal_id}`} className="inline-flex rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <ChainTag chain={record.chain} className="cursor-pointer transition-opacity hover:opacity-85" />
        </Link>
      ) : (
        <ChainTag chain={record.chain} />
      )
  },
  {
    id: "product_display",
    header: "Product",
    className: "min-w-52",
    cell: (record) =>
      record.product_key ? (
        <Link className="font-medium text-semantic-blue hover:underline" href={canonicalProductHref(record)}>
          {record.product_display}
        </Link>
      ) : (
        record.product_display
      )
  },
  { id: "headline", header: "Headline", className: "min-w-72" },
  {
    id: "signal_status",
    header: "Status",
    cell: (record) => <SignalStatusBadge status={record.signal_status} />
  },
  { id: "repeat_count", header: "Repeats", className: "text-right", headerClassName: "text-right" },
  {
    id: "impact_score",
    header: "Impact",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{formatScore(record.impact_score)}</span>,
    sortValue: (record) => record.impact_score
  }
];

export function SignalGrid({ signals }: { signals: ExecutiveSignal[] }) {
  return (
    <DataGrid
      columns={columns}
      records={signals}
      className="max-h-[58vh] focus-grid-scroll"
      emptyTitle="No signals for the current filters"
      emptyDescription="Adjust campaign, dates or search to find commercial signals."
    />
  );
}
