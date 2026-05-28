import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const severityClasses: Record<string, string> = {
  critical: "border-destructive bg-destructive text-destructive-foreground",
  high: "border-destructive text-destructive",
  medium: "border-accent bg-accent text-accent-foreground",
  low: "border-secondary bg-secondary text-secondary-foreground"
};

export function SignalSeverityBadge({ severity }: { severity?: string | null }) {
  const normalized = String(severity ?? "unknown").toLowerCase();
  return (
    <Badge className={cn("capitalize", severityClasses[normalized])}>
      {severity || "Unknown"}
    </Badge>
  );
}
