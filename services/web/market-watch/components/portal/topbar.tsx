import { LogOut, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { RoleSimulator } from "@/components/portal/role-simulator";
import { MenuPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

export function Topbar({
  menu,
  currentPath,
  compact = false,
  sidebarCollapsed = false,
  onToggleSidebar
}: {
  menu: MenuPayload;
  currentPath: string;
  compact?: boolean;
  sidebarCollapsed?: boolean;
  onToggleSidebar?: () => void;
}) {
  return (
    <header className={cn("flex items-center justify-between border-b bg-background px-5", compact ? "min-h-12" : "min-h-16")}>
      <div className="flex min-w-0 items-center gap-3">
        <Button
          type="button"
          variant="ghost"
          className="h-9 w-9 px-0"
          onClick={onToggleSidebar}
          aria-label={sidebarCollapsed ? "Expand menu" : "Collapse menu"}
          title={sidebarCollapsed ? "Expand menu" : "Collapse menu"}
        >
          {sidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </Button>
        <div className="min-w-0">
          {!compact ? <div className="text-sm text-muted-foreground">Tenant {menu.tenant.client_id}</div> : null}
          <div className="truncate font-medium">{menu.tenant.name}</div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {menu.auth.can_simulate_roles && !compact ? (
          <RoleSimulator
            activeRole={menu.user.role}
            isSimulated={menu.auth.is_role_simulated}
            currentPath={currentPath}
          />
        ) : null}
        <Badge>{menu.user.role_label}</Badge>
        <ThemeToggle />
        <form action="/api/auth/logout" method="post">
          <Button type="submit" variant="ghost" className="h-9 w-9 px-0" aria-label="Sign out" title="Sign out">
            <LogOut className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </header>
  );
}
