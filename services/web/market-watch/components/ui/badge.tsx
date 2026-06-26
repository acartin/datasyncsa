import { cn } from "@/lib/utils";

export function Badge({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[6px] border border-border-2 bg-surface-3 px-2.5 py-1 text-label font-medium text-ink-secondary",
        className
      )}
    >
      {children}
    </span>
  );
}
