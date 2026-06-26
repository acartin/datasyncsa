import Link from "next/link";
import { KeyRound } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { PasswordInput } from "@/components/ui/password-input";

export default async function ResetPasswordPage({
  searchParams
}: {
  searchParams?: Promise<{ token?: string; error?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const token = resolvedSearchParams?.token ?? "";
  const hasError = resolvedSearchParams?.error === "1";

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-10 text-foreground">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-surface-2">
              <KeyRound className="h-5 w-5 text-semantic-blue" />
            </div>
            <div>
              <div className="text-card-title font-medium">Choose a new password</div>
              <div className="text-body-sm text-muted-foreground">This link can be used only once.</div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <form action="/api/auth/reset-password" method="post" className="space-y-4">
            <input type="hidden" name="token" value={token} />
            <div className="space-y-2">
              <label htmlFor="password" className="text-body-sm font-medium">
                New password
              </label>
              <PasswordInput
                id="password"
                name="password"
                autoComplete="new-password"
                minLength={8}
                className="h-control w-full rounded-md border bg-background px-3 text-body-sm outline-none focus:ring-2 focus:ring-ring"
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="confirm_password" className="text-body-sm font-medium">
                Confirm password
              </label>
              <PasswordInput
                id="confirm_password"
                name="confirm_password"
                autoComplete="new-password"
                minLength={8}
                className="h-control w-full rounded-md border bg-background px-3 text-body-sm outline-none focus:ring-2 focus:ring-ring"
                required
              />
            </div>
            {hasError ? (
              <div className="rounded-md border border-destructive/30 bg-[var(--red-bg)] px-3 py-3 text-body-sm text-[var(--red-text)]">
                This reset link is invalid, expired, or the passwords did not match.
              </div>
            ) : null}
            <button
              type="submit"
              className="inline-flex h-control w-full items-center justify-center rounded-md bg-primary px-3 text-body-sm font-medium text-primary-foreground shadow-[0_1px_2px_var(--shadow-color)] transition-colors hover:bg-[var(--primary-hover)]"
            >
              Update password
            </button>
          </form>
          <div className="text-center text-body-sm text-muted-foreground">
            <Link href="/login" className="text-primary hover:underline">
              Back to sign in
            </Link>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
