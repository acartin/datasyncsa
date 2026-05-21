import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { roleOptions } from "@/lib/modules";
import { MenuPayload } from "@/lib/types";

export function Topbar({
  menu,
  currentPath,
  role
}: {
  menu: MenuPayload;
  currentPath: string;
  role: string;
}) {
  return (
    <header className="flex min-h-16 items-center justify-between border-b bg-background px-6">
      <div>
        <div className="text-sm text-muted-foreground">Tenant {menu.tenant.client_id}</div>
        <div className="font-medium">{menu.tenant.name}</div>
      </div>
      <div className="flex items-center gap-3">
        <div className="hidden items-center gap-2 md:flex">
          {roleOptions.map((option) => (
            <Link key={option.id} href={`${currentPath}?role=${option.id}`}>
              <Badge className={option.id === role ? "border-primary bg-primary text-primary-foreground" : ""}>
                {option.label}
              </Badge>
            </Link>
          ))}
        </div>
        <Button asChild variant="outline">
          <a href="http://192.168.10.32:8088/" target="_blank" rel="noreferrer">
            Superset
            <ExternalLink className="h-4 w-4" />
          </a>
        </Button>
      </div>
    </header>
  );
}
