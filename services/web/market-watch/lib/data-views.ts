export type DataViewDateFilter =
  | { mode: "single"; value?: string }
  | { mode: "range"; from?: string; to?: string }
  | { mode: "relative"; preset: "today" | "last_day" | "last_week" | "last_month" };

export type DataViewState = {
  search?: string;
  filters: Record<string, string[]>;
  dates?: Record<string, DataViewDateFilter>;
  sort?: Array<{ field: string; direction: "asc" | "desc" }>;
  columns?: {
    visible?: string[];
    order?: string[];
  };
};

export type SavedTableView = {
  table_view_id: number;
  view_key: string;
  label: string;
  icon?: string | null;
  color?: string | null;
  scope: "private" | "shared" | "global";
  is_favorite: boolean;
  view_order: number;
  state: DataViewState;
};

export type SavedTableViewsPayload = {
  client_id: string;
  items: SavedTableView[];
};

export function emptyDataViewState(): DataViewState {
  return { filters: {} };
}

export function compactDataViewState(state: DataViewState): DataViewState {
  const filters = Object.fromEntries(
    Object.entries(state.filters ?? {})
      .map(([key, value]) => [key, value.filter(Boolean)])
      .filter(([, value]) => Array.isArray(value) && value.length > 0)
  ) as Record<string, string[]>;
  const dates = Object.fromEntries(
    Object.entries(state.dates ?? {}).filter(([, value]) => {
      if (value.mode === "single") return Boolean(value.value);
      if (value.mode === "range") return Boolean(value.from || value.to);
      return Boolean(value.preset);
    })
  ) as Record<string, DataViewDateFilter>;

  return {
    ...(state.search?.trim() ? { search: state.search.trim() } : {}),
    filters,
    ...(Object.keys(dates).length ? { dates } : {}),
    ...(state.sort?.length ? { sort: state.sort } : {}),
    ...(state.columns ? { columns: state.columns } : {}),
  };
}

export function dataViewStateToQuery(state: DataViewState): string {
  const params = new URLSearchParams();
  const compact = compactDataViewState(state);

  if (compact.search) params.set("q", compact.search);
  Object.entries(compact.filters).forEach(([key, values]) => {
    if (values.length) params.set(key, values.join(","));
  });

  Object.entries(compact.dates ?? {}).forEach(([key, value]) => {
    if (value.mode === "single" && value.value) params.set(key, value.value);
    if (value.mode === "relative") params.set(`${key}_preset`, value.preset);
    if (value.mode === "range") {
      if (value.from) params.set(`${key}_from`, value.from);
      if (value.to) params.set(`${key}_to`, value.to);
    }
  });

  return params.toString();
}

export function dataViewStatesEqual(left: DataViewState, right: DataViewState) {
  return JSON.stringify(compactDataViewState(left)) === JSON.stringify(compactDataViewState(right));
}

export async function saveTableView(viewKey: string, label: string, state: DataViewState) {
  const response = await fetch("/api/table-views", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ view_key: viewKey, label, state: compactDataViewState(state) }),
  });
  if (!response.ok) throw new Error(`Save table view failed: ${response.status}`);
  return response.json() as Promise<{ view: SavedTableView }>;
}

export async function updateTableView(tableViewId: number, state: DataViewState) {
  const response = await fetch(`/api/table-views/${tableViewId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state: compactDataViewState(state) }),
  });
  if (!response.ok) throw new Error(`Update table view failed: ${response.status}`);
  return response.json() as Promise<{ view: SavedTableView }>;
}

export async function deleteTableView(tableViewId: number) {
  const response = await fetch(`/api/table-views/${tableViewId}`, { method: "DELETE" });
  if (!response.ok) throw new Error(`Delete table view failed: ${response.status}`);
}
