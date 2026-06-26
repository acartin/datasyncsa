import { notFound } from "next/navigation";
import { ProductIntelligencePage } from "@/components/market-watch/intraday-product-page";
import { AppShell } from "@/components/portal/app-shell";
import { getIntradayProductDetail, getMenu } from "@/lib/api";
import { normalizeClosedDateKey } from "@/lib/closed-day";

const currentPath = "/pricing/intraday-radar";

function single(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function IntradayRadarProductRoute({
  params,
  searchParams
}: {
  params: Promise<{ productKey: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ productKey }, resolvedSearchParams] = await Promise.all([params, searchParams]);
	  const filters = {
	    campaign_id: single(resolvedSearchParams?.campaign_id),
	    date_key: normalizeClosedDateKey(single(resolvedSearchParams?.date_key)),
	    chain: single(resolvedSearchParams?.chain),
	    event_id: single(resolvedSearchParams?.event_id),
	    history_days: single(resolvedSearchParams?.history_days) ?? "30"
	  };
  const [menu, payload] = await Promise.all([
    getMenu(),
    getIntradayProductDetail(productKey, filters)
  ]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <ProductIntelligencePage
        payload={payload}
        context={{
	          campaignId: filters.campaign_id,
	          dateKey: filters.date_key,
	          chain: filters.chain,
	          eventId: filters.event_id,
	          historyDays: filters.history_days,
          source: "radar",
          routeBase: "/pricing/intraday-radar/products",
          viewMode: "event",
        }}
      />
    </AppShell>
  );
}
