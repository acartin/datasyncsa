"use client";

import { Filter, Plus, Save, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { PasswordInput } from "@/components/ui/password-input";
import { ModulePayload } from "@/lib/types";
import * as React from "react";

type FieldConfig = {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  defaultValue?: string;
  minLength?: number;
  multiple?: boolean;
  options?: Array<{ value: string; label: string }>;
};

type CrudConfig = {
  title: string;
  createLabel: string;
  action: string;
  description: string;
  fields: FieldConfig[];
  submitDisabled?: boolean;
  submitLabel?: string;
};

function configForPayload(payload: ModulePayload): CrudConfig | null {
  if (payload.module.id === "settings.users") {
    return {
      title: "New user",
      createLabel: "Create user",
      action: "/api/settings/users",
      description: "API-controlled creation. The password is stored hashed.",
      fields: [
        { label: "Username", name: "username" },
        { label: "Email", name: "email", type: "email" },
        { label: "Display name", name: "display_name" },
        { label: "Temporary password", name: "password", type: "password", minLength: 8 },
        {
          label: "Role",
          name: "role_ids",
          multiple: true,
          options: [
            { value: "system-admin", label: "system-admin" },
            { value: "system-user", label: "system-user" },
            { value: "client-admin", label: "client-admin" },
            { value: "client-viewer", label: "client-viewer" }
          ]
        },
        { label: "Client ID", name: "client_id", defaultValue: payload.context.client_id }
      ]
    };
  }

  if (payload.module.id === "settings.roles") {
    return {
      title: "New role",
      createLabel: "Create role",
      action: "/api/settings/roles",
      description: "Define a business role. Granular permissions will be managed in the next step.",
      fields: [
        { label: "ID", name: "id" },
        { label: "Label", name: "label" },
        {
          label: "Scope",
          name: "scope",
          options: [
            { value: "client", label: "client" },
            { value: "system", label: "system" }
          ]
        },
        { label: "Description", name: "description", required: false }
      ]
    };
  }

  if (payload.module.id === "settings.clients") {
    return {
      title: "New client",
      createLabel: "Create client",
      action: "/api/settings/clients",
      description: "Create a tenant available for user assignment.",
      fields: [
        { label: "Key", name: "client_key" },
        { label: "Name", name: "name" },
        { label: "Market", name: "market", defaultValue: "CR" },
        {
          label: "Mode",
          name: "mode",
          options: [
            { value: "customer", label: "customer" },
            { value: "internal", label: "internal" },
            { value: "demo", label: "demo" }
          ]
        }
      ]
    };
  }

  if (payload.module.id === "operations.campaigns") {
    return {
      title: "New campaign",
      createLabel: "Create campaign",
      action: "/api/operations/campaigns",
      description: "Create a campaign and assign initial access to the active tenant.",
      fields: [
        { label: "Name", name: "name" },
        { label: "Slug", name: "slug", required: false },
        { label: "Description", name: "description", required: false },
        {
          label: "Status",
          name: "status",
          defaultValue: "active",
          options: [
            { value: "active", label: "active" },
            { value: "inactive", label: "inactive" }
          ]
        },
        {
          label: "Initial access role",
          name: "access_role",
          defaultValue: "owner",
          options: [
            { value: "owner", label: "owner" },
            { value: "admin", label: "admin" },
            { value: "viewer", label: "viewer" }
          ]
        }
      ]
    };
  }

  return null;
}

function Field({ field }: { field: FieldConfig }) {
  return (
    <label className="space-y-1 text-sm font-medium">
      <span>{field.label}</span>
      {field.options ? (
        <select
          name={field.name}
          multiple={field.multiple}
          defaultValue={field.multiple ? undefined : field.defaultValue}
          className="min-h-9 w-full rounded-md border border-border-2 bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
        >
          {field.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        field.type === "password" ? (
          <PasswordInput
            name={field.name}
            required={field.required ?? true}
            minLength={field.minLength}
            defaultValue={field.defaultValue}
            autoComplete="new-password"
            className="h-9 w-full rounded-md border border-border-2 bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
          />
        ) : (
          <input
            name={field.name}
            type={field.type ?? "text"}
            required={field.required ?? true}
            minLength={field.minLength}
            defaultValue={field.defaultValue}
            className="h-9 w-full rounded-md border border-border-2 bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
          />
        )
      )}
    </label>
  );
}

export function CrudToolbar({ payload }: { payload: ModulePayload }) {
  const [open, setOpen] = React.useState(false);
  const config = configForPayload(payload);
  if (!config) return null;

  return (
    <>
      <div className="flex flex-col gap-3 rounded-md border border-border-2 bg-card p-3 shadow-[0_1px_2px_var(--shadow-color)] md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <div className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              placeholder="Search"
              className="h-9 w-full rounded-md border border-border-2 bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
            />
          </div>
          <Button type="button" variant="outline">
            <Filter className="h-4 w-4" />
            Filters
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" disabled>
            <Save className="h-4 w-4" />
            Save
          </Button>
          <Button type="button" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" />
            {config.createLabel}
          </Button>
        </div>
      </div>

      <Modal open={open} title={config.title} description={config.description} onClose={() => setOpen(false)}>
        <form action={config.action || undefined} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            {config.fields.map((field) => (
              <Field key={field.name} field={field} />
            ))}
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={config.submitDisabled}>
              {config.submitLabel ?? "Save"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
