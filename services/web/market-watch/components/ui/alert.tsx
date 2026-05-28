import { AlertCircle, CheckCircle2, Info, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

type AlertVariant = "info" | "success" | "warning" | "error";

const icons = {
  info: Info,
  success: CheckCircle2,
  warning: TriangleAlert,
  error: AlertCircle
};

const styles = {
  info: "border-primary/30 bg-primary/10 text-foreground",
  success: "border-secondary bg-secondary text-secondary-foreground",
  warning: "border-accent/40 bg-accent/15 text-foreground",
  error: "border-destructive/30 bg-muted text-foreground"
};

export function Alert({
  variant = "info",
  title,
  children,
  className
}: {
  variant?: AlertVariant;
  title: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const Icon = icons[variant];

  return (
    <div className={cn("flex gap-3 rounded-md border px-4 py-3 text-sm", styles[variant], className)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0">
        <div className="font-medium">{title}</div>
        {children ? <div className="mt-1 text-muted-foreground">{children}</div> : null}
      </div>
    </div>
  );
}
