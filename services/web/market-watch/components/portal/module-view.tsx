"use client";

import { useMemo, useState } from "react";
import { ArrowUpRight, Database, Search, Settings2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { CrudToolbar } from "@/components/market-watch/crud-toolbar";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { KpiCard } from "@/components/market-watch/kpi-card";
import { RowActions } from "@/components/market-watch/row-actions";
import { ModulePayload } from "@/lib/types";
import { Feedback } from "@/lib/feedback";

export function ModuleView({ payload, feedback }: { payload: ModulePayload; feedback?: Feedback | null }) {
  const [catalogSearch, setCatalogSearch] = useState("");
  const hiddenColumns = new Set(["primary_role_id", "default_client_id", "client_options", "assigned_users", "assigned_permissions"]);
  if (payload.module.id === "operations.catalog-sources") {
    ["id", "chain_key", "chain_id", "category_url", "is_enabled"].forEach((column) => hiddenColumns.add(column));
  }
  const columns = Array.from(new Set(payload.records.flatMap((record) => Object.keys(record))))
    .filter((column) => !hiddenColumns.has(column))
    .slice(0, 6);
  const dataGridColumns: DataGridColumn<Record<string, unknown>>[] = columns.map((column) => ({
    id: column,
    header: column
  }));
  const catalogSearchTerm = catalogSearch
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  const filteredRecords = useMemo(() => {
    if (payload.module.id !== "operations.catalog-sources" || !catalogSearchTerm) {
      return payload.records;
    }

    return payload.records.filter((record) =>
      dataGridColumns.some((column) => {
        const value = record[column.id];
        if (value === null || value === undefined) return false;
        return String(value)
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .toLowerCase()
          .includes(catalogSearchTerm);
      })
    );
  }, [catalogSearchTerm, dataGridColumns, payload.module.id, payload.records]);
  const isCrudModule = payload.module.id.startsWith("settings.")
    || payload.module.id === "operations.campaigns"
    || payload.module.id === "operations.catalog-sources";
  const gridColumns = isCrudModule
    ? [
        ...dataGridColumns,
        {
          id: "actions",
          header: "Actions",
          headerClassName: "text-right",
          className: "w-32 text-right",
          cell: (record: Record<string, unknown>) => <RowActions payload={payload} record={record} />
        }
      ]
    : dataGridColumns;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Badge>{payload.module.status}</Badge>
            <Badge>role: {payload.context.role}</Badge>
          </div>
          <h1 className="text-2xl font-light">{payload.module.title}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            {payload.module.description}
          </p>
        </div>
        <div className="flex gap-2">
          {payload.actions.slice(0, 2).map((action) => (
            <Button key={String(action.id)} variant={action.enabled ? "default" : "outline"} disabled={!action.enabled}>
              {String(action.label)}
            </Button>
          ))}
        </div>
      </div>

      {feedback ? (
        <Alert variant={feedback.type} title={feedback.type === "error" ? "Could not save" : "Operation completed"}>
          {feedback.message}
        </Alert>
      ) : null}

      {isCrudModule ? <CrudToolbar payload={payload} /> : null}

      {!isCrudModule ? (
        <div className="grid gap-4 md:grid-cols-3">
          <KpiCard icon={Database} value={payload.records.length} label="Placeholder records" />
          <KpiCard icon={Settings2} value={payload.actions.length} label="Configured actions" />
          <KpiCard icon={ArrowUpRight} value="API" label={payload.module.id} />
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="font-medium">{isCrudModule ? "Records" : "Initial data"}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {isCrudModule ? "Search, inspect and prepare changes using the shared CRUD surface." : "Placeholder contract ready to connect to real data."}
              </div>
            </div>
            {payload.module.id === "operations.catalog-sources" ? (
              <label className="relative w-full md:w-80">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  value={catalogSearch}
                  onChange={(event) => setCatalogSearch(event.target.value)}
                  placeholder="Search catalog sources"
                  aria-label="Search catalog sources"
                  className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                />
              </label>
            ) : null}
          </div>
        </CardHeader>
        <CardContent>
          <DataGrid
            columns={gridColumns}
            records={filteredRecords}
            emptyTitle={catalogSearchTerm ? "No matching catalog sources" : "No records for this module"}
            emptyDescription={catalogSearchTerm ? "Try a different search term." : "The contract is ready to connect real data from the API."}
          />
        </CardContent>
      </Card>
    </div>
  );
}
