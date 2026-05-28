"use client";

import { Filter, Plus, Save, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
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
};

function configForPayload(payload: ModulePayload): CrudConfig | null {
  if (payload.module.id === "settings.users") {
    return {
      title: "Nuevo usuario",
      createLabel: "Crear usuario",
      action: "/api/settings/users",
      description: "Alta controlada por API. El password se almacena hasheado.",
      fields: [
        { label: "Usuario", name: "username" },
        { label: "Email", name: "email", type: "email" },
        { label: "Nombre visible", name: "display_name" },
        { label: "Password temporal", name: "password", type: "password", minLength: 8 },
        {
          label: "Rol",
          name: "role_ids",
          multiple: true,
          options: [
            { value: "system-admin", label: "system-admin" },
            { value: "system-user", label: "system-user" },
            { value: "client-admin", label: "client-admin" },
            { value: "client-viewer", label: "client-viewer" }
          ]
        },
        { label: "Cliente ID", name: "client_id", defaultValue: payload.context.client_id }
      ]
    };
  }

  if (payload.module.id === "settings.roles") {
    return {
      title: "Nuevo rol",
      createLabel: "Crear rol",
      action: "/api/settings/roles",
      description: "Define un rol de negocio. Los permisos granulares se administraran en el siguiente paso.",
      fields: [
        { label: "ID", name: "id" },
        { label: "Etiqueta", name: "label" },
        {
          label: "Scope",
          name: "scope",
          options: [
            { value: "client", label: "client" },
            { value: "system", label: "system" }
          ]
        },
        { label: "Descripcion", name: "description", required: false }
      ]
    };
  }

  if (payload.module.id === "settings.clients") {
    return {
      title: "Nuevo cliente",
      createLabel: "Crear cliente",
      action: "/api/settings/clients",
      description: "Crea un tenant disponible para asignacion de usuarios.",
      fields: [
        { label: "Clave", name: "client_key" },
        { label: "Nombre", name: "name" },
        { label: "Mercado", name: "market", defaultValue: "CR" },
        {
          label: "Modo",
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
          className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        >
          {field.options.map((option) => (
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
          defaultValue={field.defaultValue}
          className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
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
      <div className="flex flex-col gap-3 rounded-md border bg-card p-3 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <div className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              placeholder="Buscar"
              className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <Button type="button" variant="outline">
            <Filter className="h-4 w-4" />
            Filtros
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" disabled>
            <Save className="h-4 w-4" />
            Guardar
          </Button>
          <Button type="button" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" />
            {config.createLabel}
          </Button>
        </div>
      </div>

      <Modal open={open} title={config.title} description={config.description} onClose={() => setOpen(false)}>
        <form action={config.action} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            {config.fields.map((field) => (
              <Field key={field.name} field={field} />
            ))}
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit">Salvar</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
