"use client";

import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Modal({
  open,
  title,
  description,
  children,
  onClose,
  className
}: {
  open: boolean;
  title: string;
  description?: string;
  children: React.ReactNode;
  onClose: () => void;
  className?: string;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-primary/45 px-4 py-6 backdrop-blur-sm">
      <div className={cn("flex max-h-[calc(100vh-3rem)] w-full max-w-3xl flex-col rounded-[10px] border border-border-2 bg-surface text-card-foreground", className)}>
        <div className="flex items-start justify-between gap-4 border-b px-5 py-4">
          <div>
            <div className="text-base font-medium">{title}</div>
            {description ? <div className="mt-1 text-sm text-muted-foreground">{description}</div> : null}
          </div>
          <Button type="button" variant="ghost" className="h-8 w-8 px-0" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="min-h-0 overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}
