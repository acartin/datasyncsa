"use client";

import { useEffect, useMemo, useState } from "react";
import { Sidebar } from "@/components/portal/sidebar";
import { ShellStateContext } from "@/components/portal/shell-state";
import { Topbar } from "@/components/portal/topbar";
import { MenuPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

export function AppShell({
  menu,
  currentPath,
  children
}: {
  menu: MenuPayload;
  currentPath: string;
  children: React.ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [focusMode, setFocusMode] = useState(false);

  useEffect(() => {
    setSidebarCollapsed(localStorage.getItem("market-watch-sidebar") === "collapsed");
    setFocusMode(localStorage.getItem("market-watch-focus-mode") === "enabled");
  }, []);

  useEffect(() => {
    localStorage.setItem("market-watch-sidebar", sidebarCollapsed ? "collapsed" : "expanded");
  }, [sidebarCollapsed]);

  useEffect(() => {
    localStorage.setItem("market-watch-focus-mode", focusMode ? "enabled" : "disabled");
  }, [focusMode]);

  const shellState = useMemo(
    () => ({
      sidebarCollapsed,
      focusMode,
      setSidebarCollapsed,
      setFocusMode
    }),
    [sidebarCollapsed, focusMode]
  );

  return (
    <ShellStateContext.Provider value={shellState}>
      <div className={cn("group/shell flex min-h-screen", focusMode && "shell-focus")} data-focus-mode={focusMode}>
        <Sidebar menu={menu} currentPath={currentPath} collapsed={focusMode || sidebarCollapsed} />
        <div className="min-w-0 flex-1">
          <Topbar
            menu={menu}
            currentPath={currentPath}
            compact={focusMode}
            sidebarCollapsed={sidebarCollapsed}
            onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
          />
          <main className={cn("mx-auto max-w-none px-5 py-5", focusMode && "px-3 py-3")}>{children}</main>
        </div>
      </div>
    </ShellStateContext.Provider>
  );
}
