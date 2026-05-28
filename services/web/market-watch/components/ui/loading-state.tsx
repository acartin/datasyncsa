import { cn } from "@/lib/utils";

export function LoadingState({ label = "Cargando", className }: { label?: string; className?: string }) {
  return (
    <div className={cn("flex min-h-32 items-center justify-center rounded-md border bg-card text-sm text-muted-foreground", className)}>
      {label}
    </div>
  );
}
