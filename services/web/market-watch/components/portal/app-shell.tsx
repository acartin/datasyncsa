import { Sidebar } from "@/components/portal/sidebar";
import { Topbar } from "@/components/portal/topbar";
import { MenuPayload } from "@/lib/types";

export function AppShell({
  menu,
  currentPath,
  role,
  children
}: {
  menu: MenuPayload;
  currentPath: string;
  role: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <Sidebar menu={menu} currentPath={currentPath} role={role} />
      <div className="min-w-0 flex-1">
        <Topbar menu={menu} currentPath={currentPath} role={role} />
        <main className="mx-auto max-w-7xl px-6 py-6">{children}</main>
      </div>
    </div>
  );
}
