import { cn } from "@/lib/utils";

export function EmptyState({
  title = "No results",
  description,
  className
}: {
  title?: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={cn("rounded-md border border-dashed p-8 text-center", className)}>
      <div className="text-sm font-medium">{title}</div>
      {description ? <div className="mt-1 text-sm text-muted-foreground">{description}</div> : null}
    </div>
  );
}
