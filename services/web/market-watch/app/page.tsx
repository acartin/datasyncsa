import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { sessionCookieName } from "@/lib/api";

export default async function Page() {
  const cookieStore = await cookies();
  if (cookieStore.get(sessionCookieName)?.value) {
    redirect("/pricing/executive-signals");
  }

  return (
    <main className="min-h-screen bg-background px-6 py-8 text-foreground">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-6xl flex-col">
        <header className="flex min-h-14 items-center justify-between border-b">
          <div>
            <div className="text-lg font-semibold">Market Watch</div>
            <div className="text-sm text-muted-foreground">Portal operativo de pricing intelligence</div>
          </div>
          <Button asChild>
            <Link href="/login">
              Iniciar sesion
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </header>

        <section className="grid flex-1 items-center gap-6 py-10 lg:grid-cols-[1fr_380px]">
          <div className="max-w-3xl">
            <h1 className="text-3xl font-semibold tracking-normal">Inteligencia de mercado con acceso controlado por cliente</h1>
            <p className="mt-4 text-sm leading-6 text-muted-foreground">
              Consolida senales, evidencia, SKUs, cadenas y eventos en una interfaz B2B sobria. La administracion de usuarios,
              roles y clientes se resuelve desde el backend antes de exponer datos al portal.
            </p>
          </div>

          <Card>
            <CardHeader>
              <div className="font-medium">Acceso seguro</div>
              <div className="mt-1 text-sm text-muted-foreground">Fase 0 con sesiones propias y tenant server-side.</div>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <div className="flex justify-between border-b pb-2">
                <span>Autenticacion</span>
                <span className="font-medium text-foreground">Activa</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span>Registro publico</span>
                <span className="font-medium text-foreground">Deshabilitado</span>
              </div>
              <div className="flex justify-between">
                <span>Multitenant</span>
                <span className="font-medium text-foreground">API autoritativa</span>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}
