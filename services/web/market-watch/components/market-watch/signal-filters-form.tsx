import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ExecutiveSignalSearchParams, SignalFilterOption, SignalFilters } from "@/lib/pricing-types";

function SelectFilter({
  name,
  label,
  value,
  options
}: {
  name: string;
  label: string;
  value?: string;
  options: SignalFilterOption[];
}) {
  return (
    <label className="min-w-40 flex-1 space-y-1 text-xs font-medium text-muted-foreground">
      <span>{label}</span>
      <select
        name={name}
        defaultValue={value ?? ""}
        className="h-9 w-full rounded-md border bg-background px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SignalFiltersForm({
  filters,
  values
}: {
  filters: SignalFilters;
  values: ExecutiveSignalSearchParams;
}) {
  return (
    <form className="rounded-lg border bg-card p-4" action="/pricing/executive-signals">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <SelectFilter name="campaign_id" label="Campaign" value={values.campaign_id} options={filters.campaigns} />
        <label className="space-y-1 text-xs font-medium text-muted-foreground">
          <span>Date from</span>
          <input
            name="date_from"
            type="date"
            defaultValue={values.date_from ?? ""}
            className="h-9 w-full rounded-md border bg-background px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-muted-foreground">
          <span>Date to</span>
          <input
            name="date_to"
            type="date"
            defaultValue={values.date_to ?? ""}
            className="h-9 w-full rounded-md border bg-background px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-muted-foreground">
          <span>Search</span>
          <input
            name="q"
            defaultValue={values.q ?? ""}
            placeholder="Headline, product, brand, chain"
            className="h-9 w-full rounded-md border bg-background px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <SelectFilter name="brand" label="Brand" value={values.brand} options={filters.brands} />
        <SelectFilter name="chain" label="Chain" value={values.chain} options={filters.chains} />
        <SelectFilter name="signal_type" label="Signal type" value={values.signal_type} options={filters.signal_types} />
        <SelectFilter name="severity" label="Severity" value={values.severity} options={filters.severities} />
        <SelectFilter name="signal_status" label="Status" value={values.signal_status} options={filters.statuses} />
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button asChild variant="outline">
          <a href="/pricing/executive-signals">Clear</a>
        </Button>
        <Button type="submit">
          <Search className="h-4 w-4" />
          Apply
        </Button>
      </div>
    </form>
  );
}
