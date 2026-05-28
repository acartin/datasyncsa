import { notFound } from "next/navigation";
import { AppShell } from "@/components/portal/app-shell";
import { ExecutiveSignalsPage } from "@/components/market-watch/executive-signals-page";
import { getExecutiveSignals, getMenu } from "@/lib/api";
import { ExecutiveSignalSearchParams } from "@/lib/pricing-types";

const currentPath = "/pricing/executive-signals";

function normalizeSearchParams(params?: Record<string, string | string[] | undefined>): ExecutiveSignalSearchParams {
  return {
    campaign_id: single(params?.campaign_id),
    date_from: single(params?.date_from),
    date_to: single(params?.date_to),
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
  const [menu, payload] = await Promise.all([getMenu(), getExecutiveSignals(filters)]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <ExecutiveSignalsPage payload={payload} filters={filters} />
    </AppShell>
  );
}
