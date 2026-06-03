import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type KpiVariant = "blue" | "amber" | "green" | "red";

const variants: Record<KpiVariant, { bubble: string; icon: string; accent: string }> = {
  blue: { bubble: "bg-[var(--blue-bg)]", icon: "text-[var(--blue-text)]", accent: "border-l-[var(--blue-text)]" },
  amber: { bubble: "bg-[var(--amber-bg)]", icon: "text-[var(--amber-text)]", accent: "border-l-[var(--amber-text)]" },
  green: { bubble: "bg-[var(--green-bg)]", icon: "text-[var(--green-text)]", accent: "border-l-[var(--green-text)]" },
  red: { bubble: "bg-[var(--red-bg)]", icon: "text-[var(--red-text)]", accent: "border-l-[var(--red-text)]" },
};

export function KpiCard({
  label,
  value,
  icon: Icon,
  detail,
  variant = "blue",
  className
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  detail?: React.ReactNode;
  variant?: KpiVariant;
  className?: string;
}) {
  const visual = variants[variant];

  return (
    <Card className={cn("border-l-2", visual.accent, className)}>
      <CardContent className="flex min-h-24 items-start gap-3 px-4 py-3.5">
        {Icon ? (
          <div className={cn("flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-md", visual.bubble)}>
            <Icon className={cn("h-[17px] w-[17px]", visual.icon)} />
          </div>
        ) : null}
        <div className="min-w-0">
          <div className="truncate font-mono text-2xl font-normal leading-none">{value}</div>
          <div className="mt-1 text-[10px] font-normal uppercase tracking-[0.07em] text-ink-muted">{label}</div>
          {detail ? <div className={cn("mt-1 text-xs text-muted-foreground")}>{detail}</div> : null}
        </div>
      </CardContent>
    </Card>
  );
}
