import { notFound } from "next/navigation";
import { AppShell } from "@/components/portal/app-shell";
import { IntradayProductPage } from "@/components/market-watch/intraday-product-page";
import { getIntradayProductDetail, getMenu } from "@/lib/api";
import { normalizeClosedDateKey } from "@/lib/closed-day";

const currentPath = "/pricing/intraday-radar";

function single(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function IntradayProductRoute({
  params,
  searchParams
}: {
  params: Promise<{ productKey: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ productKey }, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const [menu, payload] = await Promise.all([
    getMenu(),
    getIntradayProductDetail(productKey, {
      campaign_id: single(resolvedSearchParams?.campaign_id),
      date_key: normalizeClosedDateKey(single(resolvedSearchParams?.date_key)),
      chain: single(resolvedSearchParams?.chain)
    })
  ]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <IntradayProductPage payload={payload} />
    </AppShell>
  );
}
