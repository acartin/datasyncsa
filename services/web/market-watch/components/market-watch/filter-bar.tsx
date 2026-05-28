import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type FilterOption = {
  id: string;
  label: string;
  value: string;
};

export function FilterBar({
  filters,
  actions,
  className
}: {
  filters: FilterOption[];
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3 rounded-md border bg-card p-3 md:flex-row md:items-center md:justify-between", className)}>
      <div className="flex flex-wrap gap-2">
        {filters.map((filter) => (
          <Button key={filter.id} type="button" variant="outline" className="justify-start">
            <span className="text-muted-foreground">{filter.label}</span>
            <span>{filter.value}</span>
          </Button>
        ))}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
