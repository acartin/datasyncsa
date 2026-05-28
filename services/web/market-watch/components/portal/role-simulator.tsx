import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { roleOptions } from "@/lib/modules";
import { Role } from "@/lib/types";

export function RoleSimulator({
  activeRole,
  isSimulated,
  currentPath
}: {
  activeRole: Role;
  isSimulated?: boolean;
  currentPath: string;
}) {
  return (
    <div className="hidden items-center gap-2 md:flex">
      {roleOptions.map((option) => {
        const active = option.id === activeRole;
        return (
          <form key={option.id} action="/api/auth/simulate-role" method="post">
            <input type="hidden" name="role_id" value={option.id} />
            <input type="hidden" name="redirect_to" value={currentPath} />
            <Button
              type="submit"
              variant={active ? "default" : "outline"}
              className="h-8 px-2 text-xs"
              title={`Simular ${option.label}`}
            >
              {option.label}
            </Button>
          </form>
        );
      })}
      {isSimulated ? <Badge>simulado</Badge> : null}
    </div>
  );
}
