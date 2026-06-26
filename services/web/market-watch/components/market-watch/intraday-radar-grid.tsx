"use client";

import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, ExternalLink, Minus } from "lucide-react";
import { ChainTag } from "@/components/market-watch/chain-tag";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { Button } from "@/components/ui/button";
import { changeIndicator, changeToneClass, formatEventChangeValue, formatEventValue, showChangeValue } from "@/lib/event-presentation";
import { IntradayRadarEvent } from "@/lib/pricing-types";

function ChangeIndicatorIcon({ record }: { record: IntradayRadarEvent }) {
  const indicator = changeIndicator(record);
  if (indicator === "up") return <ArrowUpRight className="h-3.5 w-3.5" />;
  if (indicator === "down") return <ArrowDownRight className="h-3.5 w-3.5" />;
  if (indicator === "flat") return <Minus className="h-3.5 w-3.5" />;
  return null;
}

function radarProductDetailHref(record: IntradayRadarEvent) {
  const search = new URLSearchParams({
    campaign_id: String(record.campaign_id),
    date_key: String(record.date_key),
    chain: record.chain,
    event_id: record.event_id,
    source: "radar",
  });
  return `/pricing/intraday-radar/products/${record.product_key}?${search.toString()}`;
}

function canonicalProductHref(record: IntradayRadarEvent) {
  const search = new URLSearchParams({ source: "radar" });
  if (record.campaign_id) search.set("campaign_id", String(record.campaign_id));
  return `/pricing/products/${record.product_key}?${search.toString()}`;
}

const columns: DataGridColumn<IntradayRadarEvent>[] = [
  { id: "business_date", header: "Date", className: "whitespace-nowrap" },
  { id: "event_area", header: "Area", className: "whitespace-nowrap" },
  {
    id: "event_type",
    header: "Event",
    className: "whitespace-nowrap",
    cell: (record) => record.presentation?.short_label ?? record.event_type
  },
  { id: "brand", header: "Brand", className: "whitespace-nowrap" },
  {
    id: "chain",
    header: "Chain",
    className: "whitespace-nowrap",
    cell: (record) =>
      record.product_key ? (
        <Link href={radarProductDetailHref(record)} className="inline-flex rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
          <ChainTag chain={record.chain} className="cursor-pointer transition-opacity hover:opacity-85" />
        </Link>
      ) : (
        <ChainTag chain={record.chain} />
      )
  },
  {
    id: "product",
    header: "Product",
    className: "min-w-80",
    cell: (record) =>
      record.product_key ? (
        <Link
          className="font-medium text-semantic-blue hover:underline"
          href={canonicalProductHref(record)}
        >
          {record.product}
        </Link>
      ) : (
        record.product
      )
  },
  {
    id: "previous_value",
    header: "Previous",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{formatEventValue(record, record.previous_value, "previous")}</span>,
    sortValue: (record) => record.previous_value
  },
  {
    id: "current_value",
    header: "Current",
    className: "text-right",
    headerClassName: "text-right",
    cell: (record) => <span className="font-mono">{formatEventValue(record, record.current_value, "current")}</span>,
    sortValue: (record) => record.current_value
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
    },
    sortValue: (record) => Math.abs(record.change_pct ?? record.change_amount ?? 0)
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

export function IntradayRadarGrid({ events }: { events: IntradayRadarEvent[] }) {
  return (
    <DataGrid
      columns={columns}
      records={events}
      className="max-h-[58vh] focus-grid-scroll"
      emptyTitle="No day-over-day movements"
      emptyDescription="No price or offer changes match the current filters."
    />
  );
}
