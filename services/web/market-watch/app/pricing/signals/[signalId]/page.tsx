import { notFound } from "next/navigation";
import { SignalDetailPage } from "@/components/market-watch/signal-detail-page";
import { AppShell } from "@/components/portal/app-shell";
import { getMenu, getSignalDetail } from "@/lib/api";

const currentPath = "/pricing/executive-signals";

export default async function SignalDetailRoute({
  params
}: {
  params: Promise<{ signalId: string }>;
}) {
  const { signalId } = await params;
  const [menu, payload] = await Promise.all([getMenu(), getSignalDetail(signalId)]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <SignalDetailPage payload={payload} />
    </AppShell>
  );
}
