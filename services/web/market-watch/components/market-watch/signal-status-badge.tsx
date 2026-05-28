import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const statusClasses: Record<string, string> = {
  new: "border-primary bg-primary text-primary-foreground",
  active: "border-accent bg-accent text-accent-foreground",
  repeated: "border-accent text-accent-foreground",
  resolved: "border-muted bg-muted text-muted-foreground"
};

export function SignalStatusBadge({ status }: { status?: string | null }) {
  const normalized = String(status ?? "unknown").toLowerCase();
  return (
    <Badge className={cn("capitalize", statusClasses[normalized])}>
      {status || "Unknown"}
    </Badge>
  );
}
