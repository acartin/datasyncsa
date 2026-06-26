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
  info: "border-border-2 bg-card text-foreground [&_svg]:text-semantic-blue",
  success: "border-border-2 bg-card text-foreground [&_svg]:text-semantic-green",
  warning: "border-border-2 bg-card text-foreground [&_svg]:text-semantic-amber",
  error: "border-border-2 bg-card text-foreground [&_svg]:text-semantic-red"
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
    <div className={cn("flex gap-3 rounded-md border px-4 py-3 text-body-sm", styles[variant], className)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0">
        <div className="text-card-title font-medium">{title}</div>
        {children ? <div className="mt-1 text-body-sm text-muted-foreground">{children}</div> : null}
      </div>
    </div>
  );
}
