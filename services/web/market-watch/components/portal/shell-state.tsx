"use client";

import { createContext, useContext } from "react";

export type ShellState = {
  sidebarCollapsed: boolean;
  focusMode: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setFocusMode: (enabled: boolean) => void;
};

export const ShellStateContext = createContext<ShellState | null>(null);

export function useShellState() {
  const context = useContext(ShellStateContext);
  if (!context) {
    return {
      sidebarCollapsed: false,
      focusMode: false,
      setSidebarCollapsed: () => undefined,
      setFocusMode: () => undefined
    };
  }
  return context;
}
