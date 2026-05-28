"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export type TabItem = {
  id: string;
  label: string;
  disabled?: boolean;
};

export function Tabs({
  items,
  value,
  onValueChange,
  className
}: {
  items: TabItem[];
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("inline-flex rounded-md border bg-card p-1", className)} role="tablist">
      {items.map((item) => {
        const active = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={item.disabled}
            onClick={() => onValueChange(item.id)}
            className={cn(
              "min-h-8 rounded-sm px-3 text-sm font-medium text-muted-foreground transition-colors disabled:pointer-events-none disabled:opacity-50",
              active && "bg-primary text-primary-foreground",
              !active && "hover:bg-muted hover:text-foreground"
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
