import { notFound } from "next/navigation";
import { AppShell } from "@/components/portal/app-shell";
import { ExecutiveSignalsPage } from "@/components/market-watch/executive-signals-page";
import { getExecutiveSignals, getMenu, getTableViews } from "@/lib/api";
import { ExecutiveSignalSearchParams } from "@/lib/pricing-types";

const currentPath = "/pricing/executive-signals";
const viewKey = "pricing.executive-signals";

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

function dateToIso(date: Date) {
  return [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, "0"),
    String(date.getUTCDate()).padStart(2, "0")
  ].join("-");
}

function relativeDateRange(preset?: string) {
  const to = costaRicaDate(-1);
  const from = new Date(to);
  if (preset === "last_week") from.setUTCDate(to.getUTCDate() - 6);
  else if (preset === "last_month") from.setUTCDate(to.getUTCDate() - 29);
  else if (preset === "last_quarter") from.setUTCDate(to.getUTCDate() - 89);
  else from.setUTCDate(to.getUTCDate());
  return { from: dateToIso(from), to: dateToIso(to) };
}

function normalizeSearchParams(params?: Record<string, string | string[] | undefined>): ExecutiveSignalSearchParams {
  const singleDate = single(params?.date);
  const preset = single(params?.date_preset);
  const dateFrom = single(params?.date_from);
  const dateTo = single(params?.date_to);
  const range = !singleDate && preset ? relativeDateRange(preset) : undefined;
  return {
    campaign_id: single(params?.campaign_id),
    date_from: singleDate ?? dateFrom ?? range?.from,
    date_to: singleDate ?? dateTo ?? range?.to,
    brand: single(params?.brand),
    chain: single(params?.chain),
    signal_type: single(params?.signal_type),
    severity: single(params?.severity),
    signal_status: single(params?.signal_status),
    q: single(params?.q),
    limit: single(params?.limit),
    offset: single(params?.offset)
  };
}

function single(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ExecutiveSignalsRoute({
  searchParams
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedSearchParams = await searchParams;
  const filters = normalizeSearchParams(resolvedSearchParams);
  const [menu, payload, saved] = await Promise.all([
    getMenu(),
    getExecutiveSignals(filters),
    getTableViews(viewKey).catch(() => ({ items: [] })),
  ]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <ExecutiveSignalsPage payload={payload} filters={filters} tableViews={saved.items} viewKey={viewKey} />
    </AppShell>
  );
}
