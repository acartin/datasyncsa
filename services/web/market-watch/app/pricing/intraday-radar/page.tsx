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

function normalizeSearchParams(params?: Record<string, string | string[] | undefined>): IntradayRadarSearchParams {
  return {
    campaign_id: single(params?.campaign_id),
    date_key: normalizeClosedDateKey(single(params?.date_key)),
    brand: single(params?.brand),
    chain: single(params?.chain),
    product_key: single(params?.product_key),
    event_area: single(params?.event_area),
    severity: single(params?.severity),
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
