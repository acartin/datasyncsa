"use client";

import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { SignalSeverityBadge } from "@/components/market-watch/signal-severity-badge";
import { SignalStatusBadge } from "@/components/market-watch/signal-status-badge";
import { Button } from "@/components/ui/button";
import { ExecutiveSignal } from "@/lib/pricing-types";

function formatScore(value: unknown) {
  if (typeof value !== "number") return "-";
  return value.toFixed(1);
}

const columns: DataGridColumn<ExecutiveSignal>[] = [
  { id: "business_date", header: "Date", className: "whitespace-nowrap" },
  {
    id: "severity",
    header: "Severity",
    cell: (record) => <SignalSeverityBadge severity={record.severity} />
  },
  { id: "signal_type", header: "Type", className: "whitespace-nowrap" },
  { id: "brand", header: "Brand", className: "whitespace-nowrap" },
  { id: "chain", header: "Chain", className: "whitespace-nowrap" },
  { id: "product_display", header: "Product", className: "min-w-52" },
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
    cell: (record) => formatScore(record.impact_score),
    sortValue: (record) => record.impact_score
  },
  {
    id: "actions",
    header: "",
    sortable: false,
    className: "text-right",
    cell: (record) => (
      <Button asChild variant="outline">
        <Link href={`/pricing/signals/${record.signal_id}`}>
          <CheckCircle2 className="h-4 w-4" />
          Validate
        </Link>
      </Button>
    )
  }
];

export function SignalGrid({ signals }: { signals: ExecutiveSignal[] }) {
  return (
    <DataGrid
      columns={columns}
      records={signals}
      className="max-h-[58vh] focus-grid-scroll"
      emptyTitle="No hay senales para los filtros actuales"
      emptyDescription="Ajusta campana, fechas o busqueda para encontrar senales comerciales."
    />
  );
}
