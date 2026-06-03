import { cn } from "@/lib/utils";

const severityClasses: Record<string, string> = {
  critical: "before:bg-semantic-red",
  high: "before:bg-semantic-red",
  medium: "before:bg-semantic-amber",
  low: "before:bg-semantic-green"
};

export function SignalSeverityBadge({ severity }: { severity?: string | null }) {
  const normalized = String(severity ?? "unknown").toLowerCase();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[12px] font-normal capitalize text-ink-secondary before:h-1.5 before:w-1.5 before:shrink-0 before:rounded-full",
        severityClasses[normalized] ?? "before:bg-ink-muted"
      )}
    >
      {severity || "Unknown"}
    </span>
  );
}
