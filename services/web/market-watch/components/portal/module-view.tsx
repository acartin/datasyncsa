"use client";

import { ArrowUpRight, Database, Settings2 } from "lucide-react";
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
  const hiddenColumns = new Set(["primary_role_id", "default_client_id", "client_options", "assigned_users", "assigned_permissions"]);
  const columns = Array.from(new Set(payload.records.flatMap((record) => Object.keys(record))))
    .filter((column) => !hiddenColumns.has(column))
    .slice(0, 6);
  const dataGridColumns: DataGridColumn<Record<string, unknown>>[] = columns.map((column) => ({
    id: column,
    header: column
  }));
  const isSettingsModule = payload.module.id.startsWith("settings.");
  const gridColumns = isSettingsModule
    ? [
        ...dataGridColumns,
        {
          id: "actions",
          header: "Acciones",
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
          <h1 className="text-2xl font-semibold">{payload.module.title}</h1>
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
        <Alert variant={feedback.type} title={feedback.type === "error" ? "No se pudo guardar" : "Operacion completada"}>
          {feedback.message}
        </Alert>
      ) : null}

      {isSettingsModule ? <CrudToolbar payload={payload} /> : null}

      {!isSettingsModule ? (
        <div className="grid gap-4 md:grid-cols-3">
          <KpiCard icon={Database} value={payload.records.length} label="Registros placeholder" />
          <KpiCard icon={Settings2} value={payload.actions.length} label="Acciones configuradas" />
          <KpiCard icon={ArrowUpRight} value="API" label={payload.module.id} />
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <div className="font-medium">Datos iniciales</div>
          <div className="mt-1 text-sm text-muted-foreground">
            Contrato placeholder listo para conectar con datos reales.
          </div>
        </CardHeader>
        <CardContent>
          <DataGrid
            columns={gridColumns}
            records={payload.records}
            emptyTitle="Sin registros para este modulo"
            emptyDescription="El contrato esta listo para conectar datos reales desde la API."
          />
        </CardContent>
      </Card>
    </div>
  );
}
