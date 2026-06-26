"use client";

import Link from "next/link";
import { Eye, FolderOpen, KeyRound, Pencil, Trash2, Users } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { PasswordInput } from "@/components/ui/password-input";
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
  resource: "users" | "clients" | "roles" | "campaigns" | "catalog-sources" | null;
  fields: FieldConfig[];
  titleField: string;
  readOnly?: boolean;
  actionBasePath?: string;
};

function configForPayload(payload: ModulePayload): RowActionConfig | null {
  if (payload.module.id === "settings.users") {
    return {
      resource: "users",
      titleField: "username",
      fields: [
        { label: "Username", name: "username", editable: false },
        { label: "Email", name: "email", type: "email", editable: false },
        { label: "Display name", name: "display_name" },
        { label: "Temporary password", name: "password", type: "password", minLength: 8, required: false, editOnly: true },
        {
          label: "Role",
          name: "role_ids",
          control: "checkbox-group",
          options: [
            { value: "system-admin", label: "system-admin" },
            { value: "system-user", label: "system-user" },
            { value: "client-admin", label: "client-admin" },
            { value: "client-viewer", label: "client-viewer" }
          ]
        },
        { label: "Client", name: "client_id", sourceName: "default_client_id", control: "select", optionsSource: "client_options" },
        {
          label: "Status",
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
        { label: "Key", name: "client_key", editable: false },
        { label: "Name", name: "name" },
        { label: "Market", name: "market" },
        {
          label: "Mode",
          name: "mode",
          options: [
            { value: "customer", label: "customer" },
            { value: "internal", label: "internal" },
            { value: "demo", label: "demo" }
          ]
        },
        {
          label: "Status",
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
        { label: "Label", name: "label" },
        {
          label: "Scope",
          name: "scope",
          options: [
            { value: "client", label: "client" },
            { value: "system", label: "system" }
          ]
        },
        { label: "Description", name: "description", required: false },
        { label: "Assigned permissions", name: "permissions", editable: false }
      ]
    };
  }

  if (payload.module.id === "settings.integrations") {
    return {
      resource: null,
      titleField: "name",
      fields: [
        { label: "ID", name: "id" },
        { label: "Name", name: "name" },
        { label: "Status", name: "status" }
      ]
    };
  }

  if (payload.module.id === "operations.campaigns") {
    return {
      resource: "campaigns",
      titleField: "name",
      actionBasePath: "/api/operations",
      fields: [
        { label: "ID", name: "id", editable: false },
        { label: "Name", name: "name" },
        { label: "Slug", name: "slug" },
        { label: "Description", name: "description", required: false },
        {
          label: "Status",
          name: "status",
          options: [
            { value: "active", label: "active" },
            { value: "inactive", label: "inactive" }
          ]
        },
        { label: "Access role", name: "access_role", editable: false },
        { label: "Default", name: "is_default", editable: false },
        { label: "Products", name: "products", editable: false },
        { label: "Locations", name: "locations", editable: false },
        { label: "Authorized clients", name: "authorized_clients", editable: false }
      ]
    };
  }

  if (payload.module.id === "operations.catalog-sources") {
    return {
      resource: "catalog-sources",
      titleField: "category_name",
      actionBasePath: "/api/operations",
      fields: [
        { label: "ID", name: "id", editable: false },
        { label: "Chain", name: "chain", editable: false },
        { label: "Engine", name: "engine", editable: false },
        { label: "Category name", name: "category_name", editable: false },
        { label: "Category slug", name: "category_slug", editable: false },
        { label: "Category URL", name: "category_url", type: "url", required: false, editable: false },
        { label: "Source reference", name: "source_category_reference", required: false, editable: false },
        {
          label: "Status",
          name: "status",
          options: [
            { value: "enabled", label: "enabled" },
            { value: "disabled", label: "disabled" }
          ]
        },
        { label: "Staged items", name: "staged_items", editable: false },
        { label: "Latest run", name: "latest_run_at", editable: false }
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
        field.type === "password" && !fieldReadOnly ? (
          <PasswordInput
            name={field.name}
            required={field.required ?? true}
            minLength={field.minLength}
            defaultValue={value}
            autoComplete="new-password"
            className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          />
        ) : (
          <input
            name={field.name}
            type={field.type ?? "text"}
            required={field.required ?? true}
            minLength={field.minLength}
            defaultValue={value}
            readOnly={fieldReadOnly}
            className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring read-only:bg-surface-2"
          />
        )
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

  const title = String(record[config.titleField] ?? record.id ?? "record");
  const actionBasePath = config.actionBasePath ?? "/api/settings";
  const canDelete = config.resource === "users" || config.resource === "clients" || config.resource === "campaigns" || config.resource === "catalog-sources";
  const canUpdate = !config.readOnly && (
    config.resource === "users"
    || config.resource === "clients"
    || config.resource === "roles"
    || config.resource === "campaigns"
    || config.resource === "catalog-sources"
  );
  const rowId = String(record.id ?? "");
  const assignedUsers = Array.isArray(record.assigned_users)
    ? (record.assigned_users as Record<string, unknown>[])
    : [];
  const assignedPermissions = Array.isArray(record.assigned_permissions)
    ? (record.assigned_permissions as Record<string, unknown>[])
    : [];
  const userColumns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "username", header: "Username" },
    { id: "email", header: "Email" },
    { id: "display_name", header: "Name" },
    { id: "status", header: "Status" }
  ];
  const permissionColumns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "id", header: "Permission" },
    { id: "label", header: "Label" },
    { id: "description", header: "Description" }
  ];

  return (
    <>
      <div className="flex justify-end gap-1">
        {config.resource === "campaigns" ? (
          <Button asChild variant="ghost" className="h-8 w-8 px-0" title="Open workspace">
            <Link href={`/operations/campaigns/${encodeURIComponent(rowId)}`}>
              <FolderOpen className="h-4 w-4" />
            </Link>
          </Button>
        ) : (
          <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="View" onClick={() => setMode("view")}>
            <Eye className="h-4 w-4" />
          </Button>
        )}
        <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Edit" onClick={() => setMode("edit")}>
          <Pencil className="h-4 w-4" />
        </Button>
        {config.resource === "roles" ? (
          <>
            <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Role users" onClick={() => setUsersOpen(true)}>
              <Users className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Role permissions" onClick={() => setPermissionsOpen(true)}>
              <KeyRound className="h-4 w-4" />
            </Button>
          </>
        ) : null}
        {canDelete ? (
          <form action={`${actionBasePath}/${config.resource}/${rowId}`} method="post">
            <input type="hidden" name="_method" value="patch" />
            <input type="hidden" name="status" value={config.resource === "catalog-sources" ? "disabled" : "inactive"} />
            <Button type="submit" variant="ghost" className="h-8 w-8 px-0" title="Deactivate">
              <Trash2 className="h-4 w-4" />
            </Button>
          </form>
        ) : (
          <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Not available" disabled>
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>

      <Modal
        open={mode !== null}
        title={`${mode === "edit" ? "Edit" : "View"} ${title}`}
        description={mode === "edit" ? undefined : "Selected record detail."}
        onClose={() => setMode(null)}
      >
        <form action={mode === "edit" && canUpdate && config.resource ? `${actionBasePath}/${config.resource}/${rowId}` : undefined} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            {config.fields.map((field) => (
              <Field key={field.name} field={field} record={record} readOnly={mode !== "edit"} />
            ))}
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setMode(null)}>
              Cancel
            </Button>
            {mode === "edit" ? <Button type="submit" disabled={!canUpdate}>{canUpdate ? "Update" : "Coming next"}</Button> : null}
          </div>
        </form>
      </Modal>

      <Modal
        open={usersOpen}
        title={`Users for ${title}`}
        description="Users assigned to this role."
        onClose={() => setUsersOpen(false)}
        className="max-w-3xl"
      >
        <DataGrid
          columns={userColumns}
          records={assignedUsers}
          emptyTitle="No assigned users"
          emptyDescription="This role does not have assigned users yet."
        />
      </Modal>

      <Modal
        open={permissionsOpen}
        title={`Permissions for ${title}`}
        description="Permissions assigned to this role."
        onClose={() => setPermissionsOpen(false)}
        className="max-w-4xl"
      >
        <DataGrid
          columns={permissionColumns}
          records={assignedPermissions}
          emptyTitle="No assigned permissions"
          emptyDescription="This role does not have assigned permissions yet."
        />
      </Modal>
    </>
  );
}
