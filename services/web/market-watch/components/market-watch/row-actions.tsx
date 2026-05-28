"use client";

import { Eye, KeyRound, Pencil, Trash2, Users } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { ModulePayload } from "@/lib/types";

type FieldConfig = {
  label: string;
  name: string;
  sourceName?: string;
  type?: string;
  required?: boolean;
  minLength?: number;
  editable?: boolean;
  editOnly?: boolean;
  control?: "input" | "select" | "checkbox-group";
  optionsSource?: string;
  options?: Array<{ value: string; label: string }>;
};

type RowActionConfig = {
  resource: "users" | "clients" | "roles" | null;
  fields: FieldConfig[];
  titleField: string;
};

function configForPayload(payload: ModulePayload): RowActionConfig | null {
  if (payload.module.id === "settings.users") {
    return {
      resource: "users",
      titleField: "username",
      fields: [
        { label: "Usuario", name: "username", editable: false },
        { label: "Email", name: "email", type: "email", editable: false },
        { label: "Nombre visible", name: "display_name" },
        { label: "Password temporal", name: "password", type: "password", minLength: 8, required: false, editOnly: true },
        {
          label: "Rol",
          name: "role_ids",
          control: "checkbox-group",
          options: [
            { value: "system-admin", label: "system-admin" },
            { value: "system-user", label: "system-user" },
            { value: "client-admin", label: "client-admin" },
            { value: "client-viewer", label: "client-viewer" }
          ]
        },
        { label: "Cliente", name: "client_id", sourceName: "default_client_id", control: "select", optionsSource: "client_options" },
        {
          label: "Estado",
          name: "status",
          options: [
            { value: "active", label: "active" },
            { value: "inactive", label: "inactive" },
            { value: "locked", label: "locked" }
          ]
        }
      ]
    };
  }

  if (payload.module.id === "settings.clients") {
    return {
      resource: "clients",
      titleField: "name",
      fields: [
        { label: "Clave", name: "client_key", editable: false },
        { label: "Nombre", name: "name" },
        { label: "Mercado", name: "market" },
        {
          label: "Modo",
          name: "mode",
          options: [
            { value: "customer", label: "customer" },
            { value: "internal", label: "internal" },
            { value: "demo", label: "demo" }
          ]
        },
        {
          label: "Estado",
          name: "status",
          options: [
            { value: "active", label: "active" },
            { value: "inactive", label: "inactive" }
          ]
        }
      ]
    };
  }

  if (payload.module.id === "settings.roles") {
    return {
      resource: "roles",
      titleField: "id",
      fields: [
        { label: "ID", name: "id", editable: false },
        { label: "Etiqueta", name: "label" },
        {
          label: "Scope",
          name: "scope",
          options: [
            { value: "client", label: "client" },
            { value: "system", label: "system" }
          ]
        },
        { label: "Descripcion", name: "description", required: false },
        { label: "Permisos asociados", name: "permissions", editable: false }
      ]
    };
  }

  if (payload.module.id === "settings.integrations") {
    return {
      resource: null,
      titleField: "name",
      fields: [
        { label: "ID", name: "id" },
        { label: "Nombre", name: "name" },
        { label: "Estado", name: "status" }
      ]
    };
  }

  return null;
}

function Field({
  field,
  record,
  readOnly
}: {
  field: FieldConfig;
  record: Record<string, unknown>;
  readOnly: boolean;
}) {
  const valueKey = field.sourceName ?? field.name;
  const value = record[valueKey] == null ? "" : String(record[valueKey]);
  const values = field.name === "role_ids" && typeof record.roles === "string"
    ? record.roles.split(",").map((item) => item.trim()).filter(Boolean)
    : [value];
  const fieldReadOnly = readOnly || field.editable === false;
  const options = field.optionsSource && Array.isArray(record[field.optionsSource])
    ? (record[field.optionsSource] as Array<{ value: string; label: string }>)
    : field.options;

  if (field.editOnly && readOnly) return null;

  return (
    <label className="space-y-1 text-sm font-medium">
      <span>{field.label}</span>
      {field.control === "checkbox-group" && options && !fieldReadOnly ? (
        <div className="grid gap-2 rounded-md border bg-background p-3">
          {options.map((option) => (
            <label key={option.value} className="flex items-center gap-2 text-sm font-normal">
              <input
                type="checkbox"
                name={field.name}
                value={option.value}
                defaultChecked={values.includes(option.value)}
                className="h-4 w-4 rounded border"
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      ) : options && !fieldReadOnly ? (
        <select
          name={field.name}
          defaultValue={value}
          className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          name={field.name}
          type={field.type ?? "text"}
          required={field.required ?? true}
          minLength={field.minLength}
          defaultValue={value}
          readOnly={fieldReadOnly}
          className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring read-only:bg-muted"
        />
      )}
    </label>
  );
}

export function RowActions({
  payload,
  record
}: {
  payload: ModulePayload;
  record: Record<string, unknown>;
}) {
  const [mode, setMode] = React.useState<"view" | "edit" | null>(null);
  const [usersOpen, setUsersOpen] = React.useState(false);
  const [permissionsOpen, setPermissionsOpen] = React.useState(false);
  const config = configForPayload(payload);
  if (!config) return null;

  const title = String(record[config.titleField] ?? record.id ?? "registro");
  const canDelete = config.resource === "users" || config.resource === "clients";
  const canUpdate = config.resource === "users" || config.resource === "clients" || config.resource === "roles";
  const rowId = String(record.id ?? "");
  const assignedUsers = Array.isArray(record.assigned_users)
    ? (record.assigned_users as Record<string, unknown>[])
    : [];
  const assignedPermissions = Array.isArray(record.assigned_permissions)
    ? (record.assigned_permissions as Record<string, unknown>[])
    : [];
  const userColumns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "username", header: "Usuario" },
    { id: "email", header: "Email" },
    { id: "display_name", header: "Nombre" },
    { id: "status", header: "Estado" }
  ];
  const permissionColumns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "id", header: "Permiso" },
    { id: "label", header: "Etiqueta" },
    { id: "description", header: "Descripcion" }
  ];

  return (
    <>
      <div className="flex justify-end gap-1">
        <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Ver" onClick={() => setMode("view")}>
          <Eye className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Editar" onClick={() => setMode("edit")}>
          <Pencil className="h-4 w-4" />
        </Button>
        {config.resource === "roles" ? (
          <>
            <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Usuarios del rol" onClick={() => setUsersOpen(true)}>
              <Users className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Permisos del rol" onClick={() => setPermissionsOpen(true)}>
              <KeyRound className="h-4 w-4" />
            </Button>
          </>
        ) : null}
        {canDelete ? (
          <form action={`/api/settings/${config.resource}/${rowId}`} method="post">
            <input type="hidden" name="_method" value="patch" />
            <input type="hidden" name="status" value="inactive" />
            <Button type="submit" variant="ghost" className="h-8 w-8 px-0" title="Desactivar">
              <Trash2 className="h-4 w-4" />
            </Button>
          </form>
        ) : (
          <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="No disponible" disabled>
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>

      <Modal
        open={mode !== null}
        title={`${mode === "edit" ? "Editar" : "Ver"} ${title}`}
        description={mode === "edit" ? undefined : "Detalle del registro seleccionado."}
        onClose={() => setMode(null)}
      >
        <form action={mode === "edit" && canUpdate && config.resource ? `/api/settings/${config.resource}/${rowId}` : undefined} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            {config.fields.map((field) => (
              <Field key={field.name} field={field} record={record} readOnly={mode !== "edit"} />
            ))}
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setMode(null)}>
              Cancelar
            </Button>
            {mode === "edit" ? <Button type="submit" disabled={!canUpdate}>Actualizar</Button> : null}
          </div>
        </form>
      </Modal>

      <Modal
        open={usersOpen}
        title={`Usuarios de ${title}`}
        description="Usuarios que tienen este rol asignado."
        onClose={() => setUsersOpen(false)}
        className="max-w-3xl"
      >
        <DataGrid
          columns={userColumns}
          records={assignedUsers}
          emptyTitle="Sin usuarios asignados"
          emptyDescription="Este rol aun no tiene usuarios asignados."
        />
      </Modal>

      <Modal
        open={permissionsOpen}
        title={`Permisos de ${title}`}
        description="Permisos asociados a este rol."
        onClose={() => setPermissionsOpen(false)}
        className="max-w-4xl"
      >
        <DataGrid
          columns={permissionColumns}
          records={assignedPermissions}
          emptyTitle="Sin permisos asignados"
          emptyDescription="Este rol aun no tiene permisos asociados."
        />
      </Modal>
    </>
  );
}
