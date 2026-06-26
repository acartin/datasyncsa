import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { LockKeyhole } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { PasswordInput } from "@/components/ui/password-input";
import { sessionCookieName } from "@/lib/api";

export default async function LoginPage({
  searchParams
}: {
  searchParams?: Promise<{ error?: string; reset?: string }>;
}) {
  const cookieStore = await cookies();
  if (cookieStore.get(sessionCookieName)?.value) {
    redirect("/pricing/executive-signals");
  }

  const resolvedSearchParams = await searchParams;
  const hasError = resolvedSearchParams?.error === "1";
  const resetSuccess = resolvedSearchParams?.reset === "1";

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-10 text-foreground">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-surface-2">
              <LockKeyhole className="h-5 w-5 text-semantic-blue" />
            </div>
            <div>
              <div className="font-medium">Market Watch</div>
              <div className="text-sm text-muted-foreground">Sign in</div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <form action="/api/auth/login" method="post" className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium">
                Username
              </label>
              <input
                id="username"
                name="username"
                autoComplete="username"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                Password
              </label>
              <PasswordInput
                id="password"
                name="password"
                autoComplete="current-password"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                required
              />
            </div>
            {hasError ? (
              <div className="rounded-md border bg-surface-2 px-3 py-2 text-sm text-foreground">
                Invalid username or password.
              </div>
            ) : null}
            {resetSuccess ? (
              <div className="rounded-md border border-border-2 bg-surface-2 px-3 py-2 text-body-sm text-foreground">
                Your password has been updated. You can sign in now.
              </div>
            ) : null}
            <div className="flex justify-end">
              <Link href="/forgot-password" className="text-body-sm text-primary hover:underline">
                Forgot password?
              </Link>
            </div>
            <Button type="submit" className="w-full">
              Sign in
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
