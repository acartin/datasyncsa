import { notFound } from "next/navigation";
import { AppShell } from "@/components/portal/app-shell";
import { MonitoredProductsPage } from "@/components/market-watch/monitored-products";
import { getMenu, getModule } from "@/lib/api";

const currentPath = "/operations/monitored-products";

export default async function MonitoredProductsRoute() {
  const [menu, payload] = await Promise.all([
    getMenu(),
    getModule("/operations/monitored-products")
  ]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <MonitoredProductsPage payload={payload} />
    </AppShell>
  );
}
