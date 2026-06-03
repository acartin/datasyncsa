import { Button } from "@/components/ui/button";
import { costaRicaYesterdayInputValue, dateKeyToInputValue } from "@/lib/closed-day";
import { IntradayRadarFilters, IntradayRadarSearchParams, SignalFilterOption } from "@/lib/pricing-types";

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
    <label className="grid gap-1 text-sm">
      <span className="font-medium">{label}</span>
      <select name={name} defaultValue={value ?? ""} className="h-10 rounded-md border bg-background px-3 text-sm">
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

export function IntradayRadarFiltersForm({
  filters,
  values
}: {
  filters: IntradayRadarFilters;
  values: IntradayRadarSearchParams;
}) {
  const defaultClosedDay = costaRicaYesterdayInputValue();
  const selectedClosedDay = dateKeyToInputValue(values.date_key) || defaultClosedDay;

  return (
    <form className="rounded-lg border bg-card p-4" action="/pricing/intraday-radar">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <SelectFilter name="campaign_id" label="Campaign" value={values.campaign_id} options={filters.campaigns} />
        <label className="grid gap-1 text-sm">
          <span className="font-medium">Closed day</span>
          <input
            type="date"
            name="date_key"
            defaultValue={selectedClosedDay}
            max={defaultClosedDay}
            className="h-10 rounded-md border bg-background px-3 text-sm"
          />
        </label>
        <SelectFilter name="brand" label="Brand" value={values.brand} options={filters.brands} />
        <SelectFilter name="chain" label="Chain" value={values.chain} options={filters.chains} />
        <label className="grid gap-1 text-sm">
          <span className="font-medium">Search</span>
          <input
            name="q"
            defaultValue={values.q ?? ""}
            className="h-10 rounded-md border bg-background px-3 text-sm"
            placeholder="Product, brand, chain"
          />
        </label>
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button asChild variant="outline">
          <a href="/pricing/intraday-radar">Clear</a>
        </Button>
        <Button type="submit">Apply</Button>
      </div>
    </form>
  );
}
