import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const statusClasses: Record<string, string> = {
  new: "bg-surface-2 text-foreground",
  active: "bg-[var(--green-bg)] text-[var(--green-text)]",
  repeated: "bg-[var(--amber-bg)] text-[var(--amber-text)]",
  resolved: "bg-surface-2 text-ink-secondary"
};

export function SignalStatusBadge({ status }: { status?: string | null }) {
  const normalized = String(status ?? "unknown").toLowerCase();
  return (
    <Badge className={cn("capitalize", statusClasses[normalized])}>
      {status || "Unknown"}
    </Badge>
  );
}
