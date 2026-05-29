"use client";

import { useMemo, useState } from "react";
import { Bookmark, Check, Filter, LayoutList, Plus, Search, SlidersHorizontal, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { cn } from "@/lib/utils";
import {
  DataViewState,
  SavedTableView,
  compactDataViewState,
  dataViewStateToQuery,
  dataViewStatesEqual,
  deleteTableView,
  saveTableView,
  updateTableView,
} from "@/lib/data-views";

export type DataViewOption = {
  id: string;
  label: string;
};

export type DataViewFilterConfig = {
  key: string;
  label: string;
  type: "select" | "multiselect" | "product";
  options: DataViewOption[];
  searchable?: boolean;
};

export type DataViewDateConfig = {
  key: string;
  label: string;
  max?: string;
};

function selectedCount(state: DataViewState) {
  return Object.values(state.filters ?? {}).reduce((count, values) => count + values.filter(Boolean).length, 0);
}

function viewHref(basePath: string, state: DataViewState) {
  const query = dataViewStateToQuery(state);
  return query ? `${basePath}?${query}` : basePath;
}

function toggleValue(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function MultiSelectField({
  field,
  values,
  onChange,
}: {
  field: DataViewFilterConfig;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const visibleOptions = useMemo(
    () =>
      field.options
        .filter((option) => !normalizedQuery || option.label.toLowerCase().includes(normalizedQuery) || option.id.toLowerCase().includes(normalizedQuery))
        .slice(0, 80),
    [field.options, normalizedQuery]
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <label className="text-sm font-medium">{field.label}</label>
        {values.length ? (
          <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => onChange([])}>
            Limpiar
          </button>
        ) : null}
      </div>
      {field.searchable || field.type === "product" ? (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            placeholder={field.type === "product" ? "Buscar producto..." : "Filtrar opciones..."}
          />
        </div>
      ) : null}
      <div className="max-h-48 overflow-auto rounded-md border bg-background p-1">
        {visibleOptions.length ? (
          visibleOptions.map((option) => {
            const active = values.includes(option.id);
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => onChange(toggleValue(values, option.id))}
                className={cn(
                  "flex w-full items-center justify-between gap-3 rounded px-2 py-1.5 text-left text-sm hover:bg-muted",
                  active && "bg-muted text-foreground"
                )}
              >
                <span className="min-w-0 truncate">{option.label}</span>
                {active ? <Check className="h-4 w-4 shrink-0 text-primary" /> : null}
              </button>
            );
          })
        ) : (
          <div className="px-2 py-6 text-center text-sm text-muted-foreground">Sin opciones</div>
        )}
      </div>
    </div>
  );
}

export function DataViewToolbar({
  basePath,
  viewKey,
  title,
  currentState,
  views,
  filters,
  dateFilters = [],
}: {
  basePath: string;
  viewKey: string;
  title: string;
  currentState: DataViewState;
  views: SavedTableView[];
  filters: DataViewFilterConfig[];
  dateFilters?: DataViewDateConfig[];
}) {
  const [workingState, setWorkingState] = useState<DataViewState>(compactDataViewState(currentState));
  const [savedViews, setSavedViews] = useState(views);
  const [filterOpen, setFilterOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [viewLabel, setViewLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [updating, setUpdating] = useState(false);
  const compactCurrent = compactDataViewState(currentState);
  const activeView = savedViews.find((view) => dataViewStatesEqual(view.state, compactCurrent));
  const changedFromCurrent = !dataViewStatesEqual(workingState, compactCurrent);
  const canUpdateActiveView = Boolean(activeView && changedFromCurrent);
  const filterCount = selectedCount(workingState);

  function updateFilter(key: string, values: string[]) {
    setWorkingState((current) => ({
      ...current,
      filters: {
        ...current.filters,
        [key]: values,
      },
    }));
  }

  function updateSingleDate(key: string, value: string) {
    setWorkingState((current) => ({
      ...current,
      dates: {
        ...(current.dates ?? {}),
        [key]: value ? { mode: "single", value } : { mode: "single" },
      },
    }));
  }

  function applyState(state = workingState) {
    window.location.href = viewHref(basePath, compactDataViewState(state));
  }

  async function handleSave() {
    if (!viewLabel.trim() || saving) return;
    setSaving(true);
    try {
      const result = await saveTableView(viewKey, viewLabel.trim(), workingState);
      setSavedViews((current) => [...current, result.view]);
      setViewLabel("");
      setSaveOpen(false);
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdateActiveView() {
    if (!activeView || updating) return;
    setUpdating(true);
    try {
      const result = await updateTableView(activeView.table_view_id, workingState);
      setSavedViews((current) => current.map((view) => (view.table_view_id === result.view.table_view_id ? result.view : view)));
      applyState(result.view.state);
    } finally {
      setUpdating(false);
    }
  }

  async function handleDelete(tableViewId: number) {
    await deleteTableView(tableViewId);
    setSavedViews((current) => current.filter((view) => view.table_view_id !== tableViewId));
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="flex min-h-14 items-center justify-between border-b bg-background">
        <div className="flex min-w-0 items-center overflow-x-auto">
          <a
            href={basePath}
            className={cn(
              "inline-flex h-14 shrink-0 items-center gap-2 border-b-2 px-4 text-sm font-medium",
              !activeView ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <LayoutList className="h-4 w-4" />
            Default
          </a>
          {savedViews.map((view) => (
            <div
              key={view.table_view_id}
              className={cn(
                "group inline-flex h-14 shrink-0 items-center gap-2 border-b-2 px-4 text-sm font-medium",
                activeView?.table_view_id === view.table_view_id
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              <a href={viewHref(basePath, view.state)} className="inline-flex min-w-0 items-center gap-2">
                <Bookmark className="h-4 w-4 shrink-0" />
                <span className="truncate">{view.label}</span>
              </a>
              <button
                type="button"
                onClick={() => handleDelete(view.table_view_id)}
                className="rounded p-0.5 opacity-0 hover:bg-muted group-hover:opacity-100"
                aria-label={`Eliminar ${view.label}`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
        <Button type="button" variant="ghost" className="mr-2 h-9 w-9 px-0" onClick={() => setSaveOpen(true)} title="Guardar vista">
          <Plus className="h-5 w-5" />
        </Button>
      </div>

      <div className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div className="text-sm font-medium">{title}</div>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
          <form
            className="relative w-full max-w-md"
            onSubmit={(event) => {
              event.preventDefault();
              applyState();
            }}
          >
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              value={workingState.search ?? ""}
              onChange={(event) => setWorkingState((current) => ({ ...current, search: event.target.value }))}
              className="h-10 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Buscar productos, marcas o cadenas"
            />
          </form>
          <Button type="button" variant="outline" className="relative h-10 w-10 px-0" onClick={() => setFilterOpen(true)} title="Filtros">
            <Filter className="h-4 w-4" />
            {filterCount ? (
              <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-primary px-1 text-xs leading-5 text-primary-foreground">{filterCount}</span>
            ) : null}
          </Button>
          <Button type="button" variant="outline" className="h-10 w-10 px-0" disabled title="Columnas">
            <SlidersHorizontal className="h-4 w-4" />
          </Button>
          {changedFromCurrent ? (
            <>
              {canUpdateActiveView ? (
                <Button type="button" variant="outline" onClick={handleUpdateActiveView} disabled={updating}>
                  {updating ? "Actualizando..." : "Actualizar vista"}
                </Button>
              ) : null}
              <Button type="button" onClick={() => applyState()}>
                Aplicar
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <Modal open={filterOpen} title="Filtros de la vista" description="Selecciona uno o varios valores por campo." onClose={() => setFilterOpen(false)}>
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            {dateFilters.map((field) => {
              const currentDate = workingState.dates?.[field.key];
              const value = currentDate?.mode === "single" ? currentDate.value ?? "" : "";
              return (
                <label key={field.key} className="grid gap-2 text-sm">
                  <span className="font-medium">{field.label}</span>
                  <input
                    type="date"
                    value={value}
                    max={field.max}
                    onChange={(event) => updateSingleDate(field.key, event.target.value)}
                    className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                  />
                </label>
              );
            })}
            {filters.map((field) => (
              <MultiSelectField
                key={field.key}
                field={field}
                values={workingState.filters?.[field.key] ?? []}
                onChange={(values) => updateFilter(field.key, values)}
              />
            ))}
          </div>
          <div className="flex justify-between gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setWorkingState({ filters: {}, search: workingState.search })}>
              <X className="h-4 w-4" />
              Limpiar filtros
            </Button>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => setFilterOpen(false)}>
                Cancelar
              </Button>
              <Button
                type="button"
                onClick={() => {
                  setFilterOpen(false);
                  applyState();
                }}
              >
                Aplicar
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal open={saveOpen} title="Guardar vista" description="Guarda search, filtros y futuros ajustes de tabla en una vista reutilizable." onClose={() => setSaveOpen(false)}>
        <div className="space-y-4">
          <label className="grid gap-1 text-sm">
            <span className="font-medium">Nombre</span>
            <input
              autoFocus
              value={viewLabel}
              onChange={(event) => setViewLabel(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && handleSave()}
              className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Ej: Megasuper alta severidad"
            />
          </label>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setSaveOpen(false)}>
              Cancelar
            </Button>
            <Button type="button" onClick={handleSave} disabled={!viewLabel.trim() || saving}>
              {saving ? "Guardando..." : activeView ? "Guardar como nueva" : "Guardar vista"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
