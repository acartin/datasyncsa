import Link from "next/link";
import { Mail } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export default async function ForgotPasswordPage({
  searchParams
}: {
  searchParams?: Promise<{ sent?: string; error?: string; debug?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const sent = resolvedSearchParams?.sent === "1";
  const hasError = resolvedSearchParams?.error === "1";
  const debugLink = resolvedSearchParams?.debug ? decodeURIComponent(resolvedSearchParams.debug) : "";

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-10 text-foreground">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-surface-2">
              <Mail className="h-5 w-5 text-semantic-blue" />
            </div>
            <div>
              <div className="text-card-title font-medium">Reset password</div>
              <div className="text-body-sm text-muted-foreground">We will send a one-time reset link to the email on file.</div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <form action="/api/auth/forgot-password" method="post" className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="login" className="text-body-sm font-medium">
                Email
              </label>
              <input
                id="login"
                name="login"
                type="email"
                autoComplete="email"
                className="h-control w-full rounded-md border bg-background px-3 text-body-sm outline-none focus:ring-2 focus:ring-ring"
                required
              />
            </div>
            {sent ? (
              <div className="rounded-md border border-border-2 bg-surface-2 px-3 py-3 text-body-sm text-foreground">
                If the account exists, a reset link has been sent.
              </div>
            ) : null}
            {hasError ? (
              <div className="rounded-md border border-destructive/30 bg-[var(--red-bg)] px-3 py-3 text-body-sm text-[var(--red-text)]">
                We could not send the reset email right now. Please try again in a moment.
              </div>
            ) : null}
            {debugLink ? (
              <div className="rounded-md border border-border-2 bg-surface-2 px-3 py-3 text-body-sm text-foreground">
                <div className="font-medium">Development reset link</div>
                <div className="mt-1 break-all text-muted-foreground">{debugLink}</div>
                <Link href={debugLink} className="mt-2 inline-flex text-primary hover:underline">
                  Open reset page
                </Link>
              </div>
            ) : null}
            <button
              type="submit"
              className="inline-flex h-control w-full items-center justify-center rounded-md bg-primary px-3 text-body-sm font-medium text-primary-foreground shadow-[0_1px_2px_var(--shadow-color)] transition-colors hover:bg-[var(--primary-hover)]"
            >
              Send reset link
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
