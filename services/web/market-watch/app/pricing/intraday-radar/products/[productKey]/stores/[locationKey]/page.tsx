import { notFound } from "next/navigation";
import { IntradayProductStorePage } from "@/components/market-watch/intraday-product-store-page";
import { AppShell } from "@/components/portal/app-shell";
import { getIntradayProductStoreDetail, getMenu } from "@/lib/api";
import { normalizeClosedDateKey } from "@/lib/closed-day";

const currentPath = "/pricing/intraday-radar";

function single(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function IntradayRadarProductStoreRoute({
  params,
  searchParams
}: {
  params: Promise<{ productKey: string; locationKey: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ productKey, locationKey }, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const filters = {
    campaign_id: single(resolvedSearchParams?.campaign_id),
    date_key: normalizeClosedDateKey(single(resolvedSearchParams?.date_key)),
    chain: single(resolvedSearchParams?.chain),
    history_days: single(resolvedSearchParams?.history_days) ?? "30"
  };
  const [menu, payload] = await Promise.all([
    getMenu(),
    getIntradayProductStoreDetail(productKey, locationKey, filters)
  ]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <IntradayProductStorePage
        payload={payload}
        productKey={productKey}
        locationKey={locationKey}
        context={{
          campaignId: filters.campaign_id,
          dateKey: filters.date_key,
          chain: filters.chain,
          historyDays: filters.history_days,
        }}
      />
    </AppShell>
  );
}
