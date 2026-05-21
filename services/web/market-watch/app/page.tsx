import { redirect } from "next/navigation";

export default async function Page({
  searchParams
}: {
  searchParams?: Promise<{ role?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const role = resolvedSearchParams?.role ?? "system-admin";
  redirect(`/analytics/dashboards?role=${role}`);
}
