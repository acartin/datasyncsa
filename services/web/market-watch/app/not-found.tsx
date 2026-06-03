import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-8">
      <div className="max-w-md text-center">
        <div className="text-sm font-medium text-muted-foreground">404</div>
        <h1 className="mt-2 text-2xl font-light">Modulo no disponible</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          La ruta no existe o tu usuario no tiene permiso para verla.
        </p>
        <Button asChild className="mt-5">
          <Link href="/pricing/executive-signals">Volver al portal</Link>
        </Button>
      </div>
    </main>
  );
}
