"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Bookmark, CalendarDays, Check, ChevronDown, Filter, LayoutList, Plus, Search, SlidersHorizontal, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { NavigationLoadingOverlay } from "@/components/market-watch/navigation-loading-overlay";
import { dateKeyToInputValue, normalizeClosedDateKey } from "@/lib/closed-day";
import { cn } from "@/lib/utils";
import {
  DataViewDateFilter,
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

const datePresets: Array<{ id: Extract<DataViewDateFilter, { mode: "relative" }>["preset"]; label: string }> = [
  { id: "last_day", label: "Last day" },
  { id: "last_week", label: "Last week" },
  { id: "last_month", label: "Last month" },
  { id: "last_quarter", label: "Last quarter" },
];

function selectedCount(state: DataViewState) {
  const filterCount = Object.values(state.filters ?? {}).reduce((count, values) => count + values.filter(Boolean).length, 0);
  const dateCount = Object.values(state.dates ?? {}).filter((value) => {
    if (value.mode === "single") return Boolean(value.value);
    if (value.mode === "range") return Boolean(value.from || value.to);
    return Boolean(value.preset);
  }).length;
  return filterCount + dateCount;
}

function viewHref(basePath: string, state: DataViewState) {
  const query = dataViewStateToQuery(state);
  return query ? `${basePath}?${query}` : basePath;
}

function toggleValue(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function inputValueToDateKey(value: string) {
  return normalizeClosedDateKey(value) ?? "";
}

function MultiSelectField({
  field,
  values,
  onChange,
  open,
  onOpenChange,
}: {
  field: DataViewFilterConfig;
  values: string[];
  onChange: (values: string[]) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
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
  const selectedLabel =
    values.length === 0
      ? "All"
      : values.length === 1
        ? field.options.find((option) => option.id === values[0])?.label ?? values[0]
        : `${values.length} selected`;

  return (
    <div className={cn("space-y-2", open && "md:col-span-2")}>
      <div className="flex items-center justify-between gap-3">
        <label className="text-sm font-medium">{field.label}</label>
        {values.length ? (
          <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => onChange([])}>
            Clear
          </button>
        ) : null}
      </div>
      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        className="flex h-9 w-full items-center justify-between gap-3 rounded-md border border-border-2 bg-background px-3 text-left text-sm outline-none hover:bg-surface-hover focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
      >
        <span className={cn("min-w-0 truncate", values.length ? "text-foreground" : "text-muted-foreground")}>{selectedLabel}</span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <div className="overflow-hidden rounded-md border border-border-2 bg-surface shadow-[0_12px_24px_var(--shadow-color)]">
          {field.searchable || field.type === "product" ? (
            <div className="border-b p-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="h-9 w-full rounded-md border border-border-2 bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
                  placeholder={field.type === "product" ? "Search product..." : "Filter options..."}
                />
              </div>
            </div>
          ) : null}
          <div className="max-h-48 overflow-auto p-1">
            {visibleOptions.length ? (
              visibleOptions.map((option) => {
                const active = values.includes(option.id);
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => onChange(toggleValue(values, option.id))}
                    className={cn(
                      "flex w-full items-center justify-between gap-3 rounded px-2 py-1.5 text-left text-sm hover:bg-surface-hover",
                      active && "bg-surface-selected text-foreground"
                    )}
                  >
                    <span className="min-w-0 truncate">{option.label}</span>
                    {active ? <Check className="h-4 w-4 shrink-0 text-semantic-blue" /> : null}
                  </button>
                );
              })
            ) : (
              <div className="px-2 py-6 text-center text-sm text-muted-foreground">No options</div>
            )}
          </div>
          <div className="flex items-center justify-between gap-3 border-t px-3 py-2">
            <span className="text-xs text-muted-foreground">{values.length ? `${values.length} selected` : "No selection"}</span>
            <Button type="button" variant="outline" className="h-8 px-3 text-xs" onClick={() => onOpenChange(false)}>
              Done
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function DateFilterField({
  field,
  value,
  onChange,
}: {
  field: DataViewDateConfig;
  value?: DataViewDateFilter;
  onChange: (value?: DataViewDateFilter) => void;
}) {
  const mode = value?.mode ?? "relative";
  const singleValue = value?.mode === "single" ? dateKeyToInputValue(value.value) : "";
  const rangeFrom = value?.mode === "range" ? dateKeyToInputValue(value.from) : "";
  const rangeTo = value?.mode === "range" ? dateKeyToInputValue(value.to) : "";
  const preset = value?.mode === "relative" ? value.preset : "last_day";

  return (
    <div className="space-y-3 rounded-md border border-border-2 bg-surface-2 p-3 md:col-span-2">
      <div className="flex items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm font-medium">
          <CalendarDays className="h-4 w-4 text-muted-foreground" />
          {field.label}
        </label>
        <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => onChange(undefined)}>
          Clear
        </button>
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        <button
          type="button"
          data-active={mode === "relative"}
          className="h-9 rounded-md border border-border-2 px-3 text-sm text-muted-foreground hover:bg-surface-hover data-[active=true]:border-primary data-[active=true]:bg-surface-selected data-[active=true]:text-foreground"
          onClick={() => onChange({ mode: "relative", preset })}
        >
          Preset
        </button>
        <button
          type="button"
          data-active={mode === "single"}
          className="h-9 rounded-md border border-border-2 px-3 text-sm text-muted-foreground hover:bg-surface-hover data-[active=true]:border-primary data-[active=true]:bg-surface-selected data-[active=true]:text-foreground"
          onClick={() => onChange({ mode: "single" })}
        >
          Single date
        </button>
        <button
          type="button"
          data-active={mode === "range"}
          className="h-9 rounded-md border border-border-2 px-3 text-sm text-muted-foreground hover:bg-surface-hover data-[active=true]:border-primary data-[active=true]:bg-surface-selected data-[active=true]:text-foreground"
          onClick={() => onChange({ mode: "range" })}
        >
          Range
        </button>
      </div>
      {mode === "relative" ? (
        <select
          value={preset}
          onChange={(event) => onChange({ mode: "relative", preset: event.target.value as Extract<DataViewDateFilter, { mode: "relative" }>["preset"] })}
          className="h-9 w-full rounded-md border border-border-2 bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
        >
          {datePresets.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      ) : null}
      {mode === "single" ? (
        <input
          type="date"
          value={singleValue}
          max={field.max}
          onChange={(event) => onChange(event.target.value ? { mode: "single", value: inputValueToDateKey(event.target.value) } : { mode: "single" })}
          className="h-9 w-full rounded-md border border-border-2 bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
        />
      ) : null}
      {mode === "range" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-xs text-muted-foreground">
            From
            <input
              type="date"
              value={rangeFrom}
              max={field.max}
              onChange={(event) => onChange({ mode: "range", from: inputValueToDateKey(event.target.value), to: value?.mode === "range" ? value.to : undefined })}
              className="h-9 rounded-md border border-border-2 bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
            />
          </label>
          <label className="grid gap-1 text-xs text-muted-foreground">
            To
            <input
              type="date"
              value={rangeTo}
              max={field.max}
              onChange={(event) => onChange({ mode: "range", from: value?.mode === "range" ? value.from : undefined, to: inputValueToDateKey(event.target.value) })}
              className="h-9 rounded-md border border-border-2 bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
            />
          </label>
        </div>
      ) : null}
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
  const router = useRouter();
  const [isNavigating, startNavigation] = useTransition();
  const [workingState, setWorkingState] = useState<DataViewState>(compactDataViewState(currentState));
  const [savedViews, setSavedViews] = useState(views);
  const [filterOpen, setFilterOpen] = useState(false);
  const [openFilterKey, setOpenFilterKey] = useState<string | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [viewLabel, setViewLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [updating, setUpdating] = useState(false);
  const compactCurrent = compactDataViewState(currentState);
  const activeView = savedViews.find((view) => dataViewStatesEqual(view.state, compactCurrent));
  const changedFromCurrent = !dataViewStatesEqual(workingState, compactCurrent);
  const canUpdateActiveView = Boolean(activeView && changedFromCurrent);
  const filterCount = selectedCount(workingState);

  useEffect(() => {
    setWorkingState(compactDataViewState(currentState));
  }, [currentState]);

  useEffect(() => {
    setSavedViews(views);
  }, [views]);

  function updateFilter(key: string, values: string[]) {
    setWorkingState((current) => ({
      ...current,
      filters: {
        ...current.filters,
        [key]: values,
      },
    }));
  }

  function updateDate(key: string, value?: DataViewDateFilter) {
    setWorkingState((current) => ({
      ...current,
      dates: Object.fromEntries(Object.entries({ ...(current.dates ?? {}), ...(value ? { [key]: value } : {}) }).filter(([dateKey]) => value || dateKey !== key)),
    }));
  }

  function applyState(state = workingState) {
    const href = viewHref(basePath, compactDataViewState(state));
    startNavigation(() => {
      router.push(href);
    });
  }

  function closeFilterModal() {
    setOpenFilterKey(null);
    setFilterOpen(false);
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
    <div className="relative overflow-hidden rounded-md border border-border-2 bg-card shadow-[0_1px_2px_var(--shadow-color)]">
      {isNavigating ? (
        <NavigationLoadingOverlay description="Fetching the selected period..." />
      ) : null}
      <div className="flex min-h-14 items-center justify-between border-b bg-surface-2">
        <div className="flex min-w-0 items-center overflow-x-auto">
          <button
            type="button"
            onClick={() => {
              startNavigation(() => {
                router.push(basePath);
              });
            }}
            className={cn(
              "inline-flex h-14 shrink-0 items-center gap-2 border-b-2 px-4 text-sm font-medium",
              !activeView ? "border-primary bg-surface-selected text-foreground" : "border-transparent text-muted-foreground hover:bg-surface-hover hover:text-foreground"
            )}
          >
            <LayoutList className="h-4 w-4" />
            Default
          </button>
          {savedViews.map((view) => (
            <div
              key={view.table_view_id}
              className={cn(
                "group inline-flex h-14 shrink-0 items-center gap-2 border-b-2 px-4 text-sm font-medium",
                activeView?.table_view_id === view.table_view_id
                  ? "border-primary bg-surface-selected text-foreground"
                  : "border-transparent text-muted-foreground hover:bg-surface-hover hover:text-foreground"
              )}
            >
              <button type="button" onClick={() => applyState(view.state)} className="inline-flex min-w-0 items-center gap-2">
                <Bookmark className="h-4 w-4 shrink-0" />
                <span className="truncate">{view.label}</span>
              </button>
              <button
                type="button"
                onClick={() => handleDelete(view.table_view_id)}
                className="rounded p-0.5 opacity-0 hover:bg-surface-hover group-hover:opacity-100"
                aria-label={`Delete ${view.label}`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
        <Button type="button" variant="ghost" className="mr-2 h-9 w-9 px-0" onClick={() => setSaveOpen(true)} title="Save view">
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
              className="h-10 w-full rounded-md border border-border-2 bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
              placeholder="Search products, brands or chains"
            />
          </form>
          <Button type="button" variant="outline" className="relative h-10 w-10 px-0" onClick={() => setFilterOpen(true)} title="Filters">
            <Filter className="h-4 w-4" />
            {filterCount ? (
              <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-primary px-1 text-xs leading-5 text-primary-foreground">{filterCount}</span>
            ) : null}
          </Button>
          <Button type="button" variant="outline" className="h-10 w-10 px-0" disabled title="Columns">
            <SlidersHorizontal className="h-4 w-4" />
          </Button>
          {changedFromCurrent ? (
            <>
              {canUpdateActiveView ? (
                <Button type="button" variant="outline" onClick={handleUpdateActiveView} disabled={updating}>
                  {updating ? "Updating..." : "Update view"}
                </Button>
              ) : null}
              <Button type="button" onClick={() => applyState()}>
                Apply
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <Modal open={filterOpen} title="View filters" description="Adjust dates, campaign, product, brand and chain." onClose={closeFilterModal}>
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            {dateFilters.map((field) => (
              <DateFilterField key={field.key} field={field} value={workingState.dates?.[field.key]} onChange={(value) => updateDate(field.key, value)} />
            ))}
            {filters.map((field) => (
              <MultiSelectField
                key={field.key}
                field={field}
                values={workingState.filters?.[field.key] ?? []}
                onChange={(values) => updateFilter(field.key, values)}
                open={openFilterKey === field.key}
                onOpenChange={(open) => setOpenFilterKey(open ? field.key : null)}
              />
            ))}
          </div>
          <div className="flex justify-between gap-2 border-t pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setOpenFilterKey(null);
                setWorkingState({ filters: {}, dates: {}, search: workingState.search });
              }}
            >
              <X className="h-4 w-4" />
              Clear filters
            </Button>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={closeFilterModal}>
                Cancel
              </Button>
              <Button
                type="button"
                onClick={() => {
                  closeFilterModal();
                  applyState();
                }}
              >
                Apply
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal open={saveOpen} title="Save view" description="Save search, filters and future table settings as a reusable view." onClose={() => setSaveOpen(false)}>
        <div className="space-y-4">
          <label className="grid gap-1 text-sm">
            <span className="font-medium">Name</span>
            <input
              autoFocus
              value={viewLabel}
              onChange={(event) => setViewLabel(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && handleSave()}
              className="h-9 rounded-md border border-border-2 bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
              placeholder="Example: Megasuper high severity"
            />
          </label>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setSaveOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={handleSave} disabled={!viewLabel.trim() || saving}>
              {saving ? "Saving..." : activeView ? "Save as new" : "Save view"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
