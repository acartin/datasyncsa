import Link from "next/link";
import { BarChart3, Boxes, Building2, ClipboardList, Cog, FolderKanban, Gauge, Link2, PackageSearch, Shield, Store, Users } from "lucide-react";
import { MenuPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

const icons: Record<string, React.ComponentType<{ className?: string }>> = {
  dashboards: BarChart3,
  reports: ClipboardList,
  campaigns: FolderKanban,
  catalogs: Boxes,
  "monitored-products": PackageSearch,
  competitors: Store,
  runs: Gauge,
  clients: Building2,
  users: Users,
  roles: Shield,
  integrations: Link2
};

export function Sidebar({
  menu,
  currentPath,
  role
}: {
  menu: MenuPayload;
  currentPath: string;
  role: string;
}) {
  return (
    <aside className="flex h-screen w-72 shrink-0 flex-col border-r bg-card">
      <div className="border-b px-5 py-4">
        <div className="text-lg font-semibold">Market Watch</div>
        <div className="mt-1 text-sm text-muted-foreground">Operations Portal</div>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {menu.sections.map((section) => (
          <div key={section.id} className="mb-5">
            <div className="mb-2 px-2 text-xs font-semibold uppercase text-muted-foreground">
              {section.label}
            </div>
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = icons[item.id] ?? Cog;
                const active = currentPath === item.href;
                return (
                  <Link
                    key={item.id}
                    href={`${item.href}?role=${role}`}
                    className={cn(
                      "flex min-h-10 items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                      active ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-muted"
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
