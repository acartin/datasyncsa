import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  icon: Icon,
  detail,
  className
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  detail?: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardContent className="flex min-h-24 items-center gap-3">
        {Icon ? <Icon className="h-5 w-5 shrink-0 text-primary" /> : null}
        <div className="min-w-0">
          <div className="truncate text-2xl font-semibold">{value}</div>
          <div className="text-sm text-muted-foreground">{label}</div>
          {detail ? <div className={cn("mt-1 text-xs text-muted-foreground")}>{detail}</div> : null}
        </div>
      </CardContent>
    </Card>
  );
}
