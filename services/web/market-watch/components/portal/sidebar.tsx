import Link from "next/link";
import { Activity, BarChart3, Boxes, Building2, ClipboardList, Cog, FolderKanban, Gauge, Link2, PackageSearch, Shield, Siren, Store, Users } from "lucide-react";
import { MenuPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

const icons: Record<string, React.ComponentType<{ className?: string }>> = {
  dashboards: BarChart3,
  "executive-signals": Siren,
  "intraday-radar": Activity,
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

const bubbleClasses: Record<string, string> = {
  dashboards: "bg-[var(--purple-bg)] text-[var(--purple-text)]",
  "executive-signals": "bg-[var(--purple-bg)] text-[var(--purple-text)]",
  "intraday-radar": "bg-[var(--purple-bg)] text-[var(--purple-text)]",
  campaigns: "bg-[var(--amber-bg)] text-[var(--amber-text)]",
  catalogs: "bg-[var(--green-bg)] text-[var(--green-text)]",
  "monitored-products": "bg-[var(--green-bg)] text-[var(--green-text)]",
  competitors: "bg-[var(--coral-bg)] text-[var(--coral-text)]",
  reports: "bg-[var(--surface-3)] text-[var(--ink-secondary)]",
  runs: "bg-[var(--surface-3)] text-[var(--ink-secondary)]",
  clients: "bg-[var(--surface-3)] text-[var(--ink-secondary)]",
  users: "bg-[var(--surface-3)] text-[var(--ink-secondary)]",
  roles: "bg-[var(--surface-3)] text-[var(--ink-secondary)]",
  integrations: "bg-[var(--surface-3)] text-[var(--ink-secondary)]",
};

export function Sidebar({
  menu,
  currentPath,
  collapsed = false
}: {
  menu: MenuPayload;
  currentPath: string;
  collapsed?: boolean;
}) {
  return (
    <aside className={cn("sticky top-0 flex h-screen shrink-0 flex-col border-r bg-surface transition-[width]", collapsed ? "w-16" : "w-72")}>
      <div className={cn("border-b py-4", collapsed ? "px-2 text-center" : "px-5")}>
        <div className={cn("font-medium", collapsed ? "text-sm" : "text-lg")}>{collapsed ? "MW" : "Market Watch"}</div>
        {!collapsed ? <div className="mt-1 text-sm text-muted-foreground">Operations Portal</div> : null}
      </div>
      <nav className={cn("flex-1 overflow-y-auto py-4", collapsed ? "px-2" : "px-3")}>
        {menu.sections.map((section) => (
          <div key={section.id} className="mb-5">
            <div className={cn("mb-2 px-2 text-[10px] font-normal uppercase tracking-[0.08em] text-ink-muted", collapsed && "sr-only")}>
              {section.label}
            </div>
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = icons[item.id] ?? Cog;
                const active = currentPath === item.href;
                const bubbleClass = bubbleClasses[item.id] ?? "bg-[var(--surface-3)] text-[var(--ink-secondary)]";
                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                      collapsed && "justify-center px-0",
                      active ? "bg-primary text-primary-foreground" : "text-ink-secondary hover:bg-surface-2 hover:text-foreground"
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-[5px] transition-colors",
                        active ? "bg-white/15 text-white" : bubbleClass
                      )}
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0" />
                    </span>
                    {!collapsed ? <span className="truncate">{item.label}</span> : null}
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
