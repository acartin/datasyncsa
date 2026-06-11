import { notFound } from "next/navigation";
import { AppShell } from "@/components/portal/app-shell";
import { MonitoredProductWorkspace } from "@/components/market-watch/monitored-products";
import { getMenu, getMonitoredProductWorkspace } from "@/lib/api";

const currentPath = "/operations/monitored-products";

export default async function MonitoredProductWorkspaceRoute({
  params,
  searchParams
}: {
  params: Promise<{ productKey: string }>;
  searchParams?: Promise<{ tab?: string }>;
}) {
  const [{ productKey }, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const [menu, payload] = await Promise.all([
    getMenu(),
    getMonitoredProductWorkspace(productKey)
  ]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <MonitoredProductWorkspace payload={payload} initialTab={resolvedSearchParams?.tab} />
    </AppShell>
  );
}
