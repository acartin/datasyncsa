import { notFound } from "next/navigation";
import { AppShell } from "@/components/portal/app-shell";
import { IntradayRadarPage } from "@/components/market-watch/intraday-radar-page";
import { getIntradayRadar, getMenu, getTableViews } from "@/lib/api";
import { normalizeClosedDateKey } from "@/lib/closed-day";
import { IntradayRadarSearchParams } from "@/lib/pricing-types";

const currentPath = "/pricing/intraday-radar";
const viewKey = "pricing.intraday-radar";

function single(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function costaRicaDate(offsetDays = 0) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Costa_Rica",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(new Date());
  const year = Number(parts.find((part) => part.type === "year")?.value);
  const month = Number(parts.find((part) => part.type === "month")?.value);
  const day = Number(parts.find((part) => part.type === "day")?.value);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + offsetDays);
  return date;
}

function dateToKey(date: Date) {
  return [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, "0"),
    String(date.getUTCDate()).padStart(2, "0")
  ].join("");
}

function relativeDateRange(preset?: string) {
  const to = costaRicaDate(-1);
  const from = new Date(to);
  if (preset === "last_week") from.setUTCDate(to.getUTCDate() - 6);
  else if (preset === "last_month") from.setUTCDate(to.getUTCDate() - 29);
  else if (preset === "last_quarter") from.setUTCDate(to.getUTCDate() - 89);
  else from.setUTCDate(to.getUTCDate());
  return { from: dateToKey(from), to: dateToKey(to) };
}

function normalizeSearchParams(params?: Record<string, string | string[] | undefined>): IntradayRadarSearchParams {
  const dateKey = normalizeClosedDateKey(single(params?.date_key));
  const preset = single(params?.date_key_preset);
  const dateKeyFrom = normalizeClosedDateKey(single(params?.date_key_from));
  const dateKeyTo = normalizeClosedDateKey(single(params?.date_key_to));
  const datePreset =
    preset === "today" || preset === "last_day" || preset === "last_week" || preset === "last_month" || preset === "last_quarter"
      ? preset
      : !dateKey && !dateKeyFrom && !dateKeyTo
        ? "last_day"
        : undefined;
  const range = dateKey ? undefined : datePreset ? relativeDateRange(datePreset) : undefined;
  return {
    campaign_id: single(params?.campaign_id),
    date_key: dateKey,
    date_key_from: dateKey ? undefined : dateKeyFrom ?? range?.from,
    date_key_to: dateKey ? undefined : dateKeyTo ?? range?.to,
    date_key_preset: datePreset,
    brand: single(params?.brand),
    chain: single(params?.chain),
    product_key: single(params?.product_key),
    q: single(params?.q),
    limit: single(params?.limit),
    offset: single(params?.offset)
  };
}

export default async function IntradayRadarRoute({
  searchParams
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedSearchParams = await searchParams;
  const filters = normalizeSearchParams(resolvedSearchParams);
  const [menu, payload, saved] = await Promise.all([
    getMenu(),
    getIntradayRadar(filters),
    getTableViews(viewKey).catch(() => ({ items: [] })),
  ]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <IntradayRadarPage payload={payload} filters={filters} tableViews={saved.items} viewKey={viewKey} />
    </AppShell>
  );
}
