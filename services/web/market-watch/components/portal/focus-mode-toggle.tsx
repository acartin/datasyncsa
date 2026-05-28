"use client";

import { Maximize2, Minimize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useShellState } from "@/components/portal/shell-state";

export function FocusModeToggle() {
  const { focusMode, setFocusMode } = useShellState();

  return (
    <Button
      type="button"
      variant="outline"
      className="h-9 w-9 px-0"
      onClick={() => setFocusMode(!focusMode)}
      aria-label={focusMode ? "Restaurar vista" : "Maximizar grid"}
      title={focusMode ? "Restaurar vista" : "Maximizar grid"}
    >
      {focusMode ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
    </Button>
  );
}
