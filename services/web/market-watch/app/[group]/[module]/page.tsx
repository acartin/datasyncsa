import { notFound } from "next/navigation";
import { AppShell } from "@/components/portal/app-shell";
import { ModuleView } from "@/components/portal/module-view";
import { getMenu, getModule } from "@/lib/api";
import { moduleEndpointByPath } from "@/lib/modules";
import { Role } from "@/lib/types";

const validRoles = new Set(["client-admin", "client-viewer", "system-admin", "system-user"]);

function normalizeRole(role?: string): Role {
  return validRoles.has(role ?? "") ? (role as Role) : "system-admin";
}

export default async function ModulePage({
  params,
  searchParams
}: {
  params: Promise<{ group: string; module: string }>;
  searchParams?: Promise<{ role?: string }>;
}) {
  const resolvedParams = await params;
  const resolvedSearchParams = await searchParams;
  const role = normalizeRole(resolvedSearchParams?.role);
  const currentPath = `/${resolvedParams.group}/${resolvedParams.module}`;
  const endpoint = moduleEndpointByPath[currentPath];
  if (!endpoint) notFound();

  const [menu, payload] = await Promise.all([getMenu(role), getModule(endpoint, role)]);
  const allowed = menu.sections.some((section) => section.items.some((item) => item.href === currentPath));
  if (!allowed) notFound();

  return (
    <AppShell menu={menu} currentPath={currentPath} role={role}>
      <ModuleView payload={payload} />
    </AppShell>
  );
}
