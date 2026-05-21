import { ArrowUpRight, Database, Settings2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ModulePayload } from "@/lib/types";

function renderValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "Si" : "No";
  if (value === null || value === undefined) return "-";
  return String(value);
}

export function ModuleView({ payload }: { payload: ModulePayload }) {
  const columns = Array.from(new Set(payload.records.flatMap((record) => Object.keys(record)))).slice(0, 6);

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

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-3">
            <Database className="h-5 w-5 text-primary" />
            <div>
              <div className="text-2xl font-semibold">{payload.records.length}</div>
              <div className="text-sm text-muted-foreground">Registros placeholder</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3">
            <Settings2 className="h-5 w-5 text-primary" />
            <div>
              <div className="text-2xl font-semibold">{payload.actions.length}</div>
              <div className="text-sm text-muted-foreground">Acciones configuradas</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3">
            <ArrowUpRight className="h-5 w-5 text-primary" />
            <div>
              <div className="text-2xl font-semibold">API</div>
              <div className="text-sm text-muted-foreground">{payload.module.id}</div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="font-medium">Datos iniciales</div>
          <div className="mt-1 text-sm text-muted-foreground">
            Contrato placeholder listo para conectar con datos reales.
          </div>
        </CardHeader>
        <CardContent>
          {payload.records.length ? (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    {columns.map((column) => (
                      <th key={column} className="px-3 py-2 font-medium">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {payload.records.map((record, index) => (
                    <tr key={index} className="border-b last:border-0">
                      {columns.map((column) => (
                        <td key={column} className="px-3 py-3">
                          {renderValue(record[column])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
              Sin registros para este modulo.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
