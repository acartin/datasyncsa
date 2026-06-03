import { redirect } from "next/navigation";

export default async function IntradayProductRoute({
  params,
  searchParams
}: {
  params: Promise<{ productKey: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ productKey }, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const nextParams = new URLSearchParams();
  Object.entries(resolvedSearchParams ?? {}).forEach(([key, value]) => {
    const normalized = Array.isArray(value) ? value[0] : value;
    if (normalized) nextParams.set(key, normalized);
  });
  if (!nextParams.has("source")) nextParams.set("source", "radar");
  redirect(`/pricing/products/${encodeURIComponent(productKey)}?${nextParams.toString()}`);
}
