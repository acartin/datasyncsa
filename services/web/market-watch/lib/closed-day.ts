export function costaRicaYesterdayDateKey() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Costa_Rica",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(new Date());
  const year = Number(parts.find((part) => part.type === "year")?.value);
  const month = Number(parts.find((part) => part.type === "month")?.value);
  const day = Number(parts.find((part) => part.type === "day")?.value);
  const costaRicaToday = new Date(Date.UTC(year, month - 1, day));
  costaRicaToday.setUTCDate(costaRicaToday.getUTCDate() - 1);
  return [
    costaRicaToday.getUTCFullYear(),
    String(costaRicaToday.getUTCMonth() + 1).padStart(2, "0"),
    String(costaRicaToday.getUTCDate()).padStart(2, "0")
  ].join("");
}

export function dateKeyToInputValue(value?: string | number | null) {
  if (!value) return "";
  const compact = String(value).replaceAll("-", "");
  if (!/^\d{8}$/.test(compact)) return "";
  return `${compact.slice(0, 4)}-${compact.slice(4, 6)}-${compact.slice(6, 8)}`;
}

export function costaRicaYesterdayInputValue() {
  return dateKeyToInputValue(costaRicaYesterdayDateKey());
}

export function normalizeClosedDateKey(value: string | undefined) {
  if (!value) return undefined;
  const compact = value.replaceAll("-", "").trim();
  return /^\d{8}$/.test(compact) ? compact : undefined;
}
