import { notFound } from "next/navigation";
import { CampaignWorkspace } from "@/components/market-watch/campaign-workspace";
import { AppShell } from "@/components/portal/app-shell";
import { getCampaignWorkspace, getMenu } from "@/lib/api";
import { feedbackFromSearchParams } from "@/lib/feedback";

const currentPath = "/operations/campaigns";

export default async function CampaignWorkspaceRoute({
  params,
  searchParams
}: {
  params: Promise<{ campaignId: string }>;
  searchParams?: Promise<{ feedback?: string; message?: string; tab?: string; business_date?: string }>;
}) {
  const { campaignId } = await params;
  const resolvedSearchParams = await searchParams;
  const [menu, payload] = await Promise.all([
    getMenu(),
    getCampaignWorkspace(campaignId, resolvedSearchParams?.business_date)
  ]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath}>
      <CampaignWorkspace
        payload={payload}
        feedback={feedbackFromSearchParams(resolvedSearchParams)}
        initialTab={resolvedSearchParams?.tab}
      />
    </AppShell>
  );
}
