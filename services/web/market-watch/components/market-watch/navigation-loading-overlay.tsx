import { Loader2 } from "lucide-react";

type NavigationLoadingOverlayProps = {
  title?: string;
  description?: string;
};

export function NavigationLoadingOverlay({
  title = "Updating view",
  description = "Fetching the selected data...",
}: NavigationLoadingOverlayProps) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-background/55 backdrop-blur-[2px]" role="status" aria-live="polite">
      <div className="flex min-w-72 flex-col items-center gap-3 rounded-lg border border-border-2 bg-card px-6 py-5 text-center shadow-[0_18px_48px_var(--shadow-color)]">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <div>
          <div className="text-sm font-medium text-foreground">{title}</div>
          <div className="mt-1 text-xs text-muted-foreground">{description}</div>
        </div>
      </div>
    </div>
  );
}
