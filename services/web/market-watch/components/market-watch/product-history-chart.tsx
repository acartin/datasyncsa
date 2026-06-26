"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart, Bar, Scatter,
} from "recharts";
import { IntradayProductHistoryPoint, IntradayProductDailyPoint, IntradayProductPricePoint } from "@/lib/pricing-types";

function currency(value: number) {
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function timeLabel(value: string) {
  return value.includes("T") ? value.slice(11, 16) : value.slice(11, 16) || value;
}

function compactDate(value: string) {
  return value.slice(5);
}

const chainColors: Record<string, string> = {
  walmart: "var(--chart-orange)",
  "maxi palí": "var(--chart-green)",
  "maxi pali": "var(--chart-green)",
  "más x menos": "var(--chart-blue)",
  "mas x menos": "var(--chart-blue)",
  megasuper: "var(--chart-teal)",
};

const fallbackChartColors = ["var(--chart-orange)", "var(--chart-green)", "var(--chart-blue)", "var(--chart-teal)", "var(--chart-rose)", "var(--chart-violet)"];

function seriesColor(chainOrIndex: string | number) {
  if (typeof chainOrIndex === "string") {
    return chainColors[chainOrIndex.trim().toLowerCase()] ?? fallbackChartColors[0];
  }
  return fallbackChartColors[chainOrIndex % fallbackChartColors.length];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const formatTooltip: any = (value: number) => currency(value);

export function ProductHistoryChart({ history }: { history: IntradayProductHistoryPoint[] }) {
  const priced = history.filter((item) => typeof item.average_price === "number");
  const chains = Array.from(new Set(priced.map((item) => item.chain))).slice(0, 4);

  if (!priced.length) {
    return <div className="flex min-h-48 items-center justify-center text-sm text-muted-foreground">No historical price data to chart.</div>;
  }

  const data = Array.from(new Set(priced.map((item) => item.captured_at_cr))).sort().map((capture) => {
    const row: Record<string, string | number | null> = { capture: timeLabel(capture) };
    chains.forEach((chain) => {
      const point = priced.find((p) => p.chain === chain && p.captured_at_cr === capture);
      row[chain] = point?.average_price ?? null;
    });
    return row;
  });

  return (
    <div className="overflow-x-auto">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 20, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="0" stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="capture" tick={{ fontSize: 10, fill: "var(--ink-muted)" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "var(--ink-muted)" }} axisLine={false} tickLine={false} tickFormatter={formatTooltip} width={72} />
          <Tooltip formatter={formatTooltip} contentStyle={{ background: "var(--surface)", border: "1px solid var(--border-2)", borderRadius: 8, boxShadow: "0 12px 24px var(--shadow-color)", fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {chains.map((chain, i) => (
            <Line key={chain} type="monotone" dataKey={chain} stroke={seriesColor(chain)} strokeWidth={1} dot={false} activeDot={{ r: 2.5, strokeWidth: 0 }} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ProductDailyHistoryChart({ history }: { history: IntradayProductDailyPoint[] }) {
  const priced = history.filter((item) => typeof item.average_price === "number");
  const chains = Array.from(new Set(priced.map((item) => item.chain))).slice(0, 4);
  const dates = Array.from(new Set(priced.map((item) => item.business_date))).sort();

  if (!priced.length) {
    return <div className="flex min-h-48 items-center justify-center text-sm text-muted-foreground">No daily history to chart.</div>;
  }

  const data = dates.map((date) => {
    const row: Record<string, string | number | null> = { date: compactDate(date) };
    chains.forEach((chain) => {
      const point = priced.find((p) => p.chain === chain && p.business_date === date);
      row[chain] = point?.average_price ?? null;
    });
    return row;
  });

  return (
    <div className="overflow-x-auto">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 20, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="0" stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--ink-muted)" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "var(--ink-muted)" }} axisLine={false} tickLine={false} tickFormatter={formatTooltip} width={72} />
          <Tooltip formatter={formatTooltip} contentStyle={{ background: "var(--surface)", border: "1px solid var(--border-2)", borderRadius: 8, boxShadow: "0 12px 24px var(--shadow-color)", fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {chains.map((chain, i) => (
            <Line key={chain} type="monotone" dataKey={chain} stroke={seriesColor(chain)} strokeWidth={1} dot={false} activeDot={{ r: 2.5, strokeWidth: 0 }} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ProductPromoTimelineChart({ history }: { history: IntradayProductHistoryPoint[] }) {
  const points = history.filter((item) => item.captured_at_cr).sort((a, b) => a.captured_at_cr.localeCompare(b.captured_at_cr));
  const chains = Array.from(new Set(points.map((item) => item.chain))).slice(0, 5);

  if (!points.length) {
    return <div className="flex min-h-32 items-center justify-center text-sm text-muted-foreground">No intraday captures to chart.</div>;
  }

  const captures = Array.from(new Set(points.map((item) => item.captured_at_cr))).sort();
  const data = captures.map((capture) => {
    const row: Record<string, string | number | null> = { capture: timeLabel(capture) };
    chains.forEach((chain) => {
      const point = points.find((p) => p.chain === chain && p.captured_at_cr === capture);
      row[chain] = point?.average_price ?? null;
      row[`${chain}_promo`] = point?.promo_detected ? 1 : 0;
    });
    return row;
  });

  return (
    <div className="overflow-x-auto">
      <div className="mb-3 flex flex-wrap gap-4 text-xs">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-semantic-green" />
          <span>Active promo</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full border border-muted-foreground bg-background" />
          <span>No promo</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={chains.length * 50 + 40}>
        <ComposedChart data={data} margin={{ top: 8, right: 20, bottom: 8, left: 8 }} layout="vertical">
          <CartesianGrid strokeDasharray="0" stroke="var(--chart-grid)" opacity={0.8} vertical={false} />
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="capture" tick={{ fontSize: 11 }} stroke="var(--ink-muted)" width={60} />
          <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border-2)", borderRadius: 8, boxShadow: "0 12px 24px var(--shadow-color)", fontSize: 13 }} />
          {chains.map((chain, i) => (
            <Bar key={chain} dataKey={`${chain}_promo`} fill="var(--green)" opacity={0.7} stackId={chain} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

type ProductPriceMode = "regular" | "promo" | "both";

type PriceTimelineRow = {
  date: string;
  full_date: string;
} & Record<string, string | number | boolean | null>;

function numericValue(value: unknown) {
  return typeof value === "number" ? value : null;
}

function booleanValue(value: unknown) {
  return typeof value === "boolean" ? value : null;
}

function availabilityState(value: unknown) {
  return value === "available" || value === "listed_unavailable" || value === "unobserved" ? value : null;
}

function unavailableMarkerValue(index: number) {
  return 12 + index * 8;
}

function availabilityMessage(row: PriceTimelineRow, chain: string) {
  const state = availabilityState(row[`${chain}__availability`]);
  if (state === "listed_unavailable") {
    const visible = numericValue(row[`${chain}__visible_locations`]);
    const available = numericValue(row[`${chain}__available_locations`]);
    const listed = booleanValue(row[`${chain}__is_listed`]);
    const availableFlag = booleanValue(row[`${chain}__is_available`]);
    if (visible !== null && available !== null) {
      return {
        tone: "unavailable" as const,
        text: `${available}/${visible} stores available`,
      };
    }
    if (listed === true && availableFlag === false) {
      return {
        tone: "unavailable" as const,
        text: "Listed, not available",
      };
    }
    return {
      tone: "unavailable" as const,
      text: "Unavailable",
    };
  }
  if (state === "unobserved") {
    return {
      tone: "unobserved" as const,
      text: "No listing or observation",
    };
  }
  return null;
}

function AvailabilityMarker({
  cx,
  cy,
}: {
  cx?: number;
  cy?: number;
}) {
  if (typeof cx !== "number" || typeof cy !== "number") return null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={4} fill="var(--red-bg)" stroke="var(--red)" strokeWidth={1.5} />
      <circle cx={cx} cy={cy} r={1.25} fill="var(--red)" />
    </g>
  );
}

function PriceTimelineTooltip({
  active,
  payload,
  chains,
  priceMode,
}: {
  active?: boolean;
  payload?: Array<{ payload?: PriceTimelineRow }>;
  chains: string[];
  priceMode: ProductPriceMode;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;

  const sections = chains
    .map((chain) => {
      const regular = numericValue(row[`${chain}__regular`]);
      const promo = numericValue(row[`${chain}__promo`]);
      const availability = availabilityMessage(row, chain);
      const showRegular = priceMode !== "promo" && regular !== null;
      const showPromo = priceMode !== "regular" && promo !== null;
      if (!showRegular && !showPromo && !availability) return null;
      return {
        chain,
        color: seriesColor(chain),
        regular,
        promo,
        showRegular,
        showPromo,
        availability,
      };
    })
    .filter((section): section is NonNullable<typeof section> => section !== null);

  if (!sections.length) return null;

  return (
    <div className="min-w-56 rounded-[8px] border border-border-2 bg-card px-3 py-2 shadow-[0_12px_24px_var(--shadow-color)]">
      <div className="mb-2 text-[11px] font-medium text-foreground">{row.full_date}</div>
      <div className="space-y-2">
        {sections.map((section) => (
          <div key={section.chain} className="space-y-1">
            <div className="flex items-center gap-2 text-[11px] font-medium text-foreground">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: section.color }}
              />
              <span>{section.chain}</span>
            </div>
            {section.showRegular ? (
              <div className="flex items-center justify-between gap-4 text-[11px] text-ink-secondary">
                <span>Regular</span>
                <span className="font-mono text-foreground">{currency(section.regular as number)}</span>
              </div>
            ) : null}
            {section.showPromo ? (
              <div className="flex items-center justify-between gap-4 text-[11px] text-ink-secondary">
                <span>Promo</span>
                <span className="font-mono text-foreground">{currency(section.promo as number)}</span>
              </div>
            ) : null}
            {section.availability ? (
              <div
                className="rounded-[6px] border px-2 py-1 text-[11px]"
                style={{
                  borderColor: section.availability.tone === "unavailable" ? "var(--red)" : "var(--border-2)",
                  background: section.availability.tone === "unavailable" ? "var(--red-bg)" : "var(--surface-2)",
                  color: section.availability.tone === "unavailable" ? "var(--red-text)" : "var(--ink-secondary)",
                }}
              >
                {section.availability.text}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function CombinedPriceChart({
  points,
  selectedChains,
  priceMode = "both",
}: {
  points: IntradayProductPricePoint[];
  selectedChains?: string[];
  priceMode?: ProductPriceMode;
}) {
  const chains = selectedChains ?? Array.from(new Set(points.map((point) => point.chain))).sort();
  const filtered = points.filter((point) => chains.includes(point.chain));
  const priced = filtered.filter((p) => typeof p.reference_price_amount === "number" || typeof p.promo_price_amount === "number");

  if (!filtered.length) {
    return (
      <div className="rounded-md border border-border-2 bg-background p-4">
        <div className="mb-3 text-sm font-medium">Price history by chain</div>
        <div className="flex min-h-40 items-center justify-center text-sm text-muted-foreground">No prices or availability signals to chart.</div>
      </div>
    );
  }

  const pointsByKey = new Map(filtered.map((point) => [`${point.chain}::${point.business_date}`, point] as const));
  const businessDates = Array.from(new Set(filtered.map((point) => point.business_date))).sort();
  const data: PriceTimelineRow[] = businessDates.map((businessDate) => {
    const row: PriceTimelineRow = { date: compactDate(businessDate), full_date: businessDate };
    chains.forEach((chain, index) => {
      const point = pointsByKey.get(`${chain}::${businessDate}`);
      row[`${chain}__regular`] = point?.reference_price_amount ?? null;
      row[`${chain}__promo`] = point?.promo_detected ? point?.promo_price_amount ?? null : null;
      row[`${chain}__availability`] = point?.availability_state ?? null;
      row[`${chain}__visible_locations`] = point?.visible_locations ?? null;
      row[`${chain}__available_locations`] = point?.available_locations ?? null;
      row[`${chain}__is_listed`] = point?.is_listed ?? null;
      row[`${chain}__is_available`] = point?.is_available ?? null;
      row[`${chain}__unavailable_marker`] =
        point?.availability_state === "listed_unavailable" ? unavailableMarkerValue(index) : null;
    });
    return row;
  });
  const numericSeries = priced.flatMap((point) => [
    point.reference_price_amount,
    point.promo_price_amount,
  ]).filter((value): value is number => typeof value === "number");
  const markerCeiling = unavailableMarkerValue(Math.max(chains.length - 1, 0)) + 12;
  const yAxisMax = numericSeries.length
    ? Math.max(Math.ceil(Math.max(...numericSeries) * 1.1), markerCeiling)
    : markerCeiling;

  return (
    <div className="rounded-md border border-border-2 bg-card px-4 py-4 shadow-[0_1px_2px_var(--shadow-color)]">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-[13px] font-medium">Price timeline</div>
          <div className="mt-1 text-[11px] text-ink-muted">Regular and promotional prices across chains.</div>
        </div>
        <div className="text-xs text-muted-foreground">{businessDates.length} days · {chains.length} chains</div>
      </div>
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="0" stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--ink-muted)" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis domain={[0, yAxisMax]} tick={{ fontSize: 10, fill: "var(--ink-muted)" }} axisLine={false} tickLine={false} tickFormatter={formatTooltip} width={72} />
          <Tooltip
            content={<PriceTimelineTooltip chains={chains} priceMode={priceMode} />}
            cursor={{ stroke: "var(--border-2)", strokeWidth: 1 }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--ink-muted)" }} />
          {chains.flatMap((chain) => {
            const color = seriesColor(chain);
            const lines = [];
            if (priceMode === "regular" || priceMode === "both") {
              lines.push(
                <Line
                  key={`${chain}-regular`}
                  type="monotone"
                  dataKey={`${chain}__regular`}
                  stroke={color}
                  strokeWidth={1}
                  dot={false}
                  activeDot={{ r: 2.5, strokeWidth: 0 }}
                  name={`${chain} regular`}
                />
              );
            }
            if (priceMode === "promo" || priceMode === "both") {
              lines.push(
                <Line
                  key={`${chain}-promo`}
                  type="monotone"
                  dataKey={`${chain}__promo`}
                  stroke={color}
                  strokeWidth={1}
                  strokeDasharray="4 3"
                  dot={false}
                  activeDot={{ r: 2.5, strokeWidth: 0 }}
                  name={`${chain} promo`}
                />
              );
            }
            return lines;
          })}
          {chains.map((chain) => (
            <Scatter
              key={`${chain}-unavailable`}
              dataKey={`${chain}__unavailable_marker`}
              fill="var(--red)"
              shape={<AvailabilityMarker />}
              legendType="none"
              isAnimationActive={false}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ProductNormalPromoPriceCharts({
  history,
  selectedChains,
  priceMode = "both",
}: {
  history: IntradayProductPricePoint[];
  selectedChains?: string[];
  priceMode?: ProductPriceMode;
}) {
  return (
    <div className="overflow-x-auto">
      <CombinedPriceChart points={history} selectedChains={selectedChains} priceMode={priceMode} />
    </div>
  );
}
