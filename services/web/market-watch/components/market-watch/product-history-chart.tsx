"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart, Bar,
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
  walmart: "#ff7300",
  "maxi palí": "#387908",
  "maxi pali": "#387908",
  "más x menos": "#3b5bdb",
  "mas x menos": "#3b5bdb",
  megasuper: "#2a9d8f",
};

const fallbackChartColors = ["#ff7300", "#387908", "#3b5bdb", "#2a9d8f", "#c84c09", "#4c6f2a"];

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
          <Tooltip formatter={formatTooltip} contentStyle={{ background: "var(--surface)", border: "0.5px solid var(--border-2)", borderRadius: 8, boxShadow: "none", fontSize: 12 }} />
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
          <Tooltip formatter={formatTooltip} contentStyle={{ background: "var(--surface)", border: "0.5px solid var(--border-2)", borderRadius: 8, boxShadow: "none", fontSize: 12 }} />
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
          <Tooltip contentStyle={{ fontSize: 13 }} />
          {chains.map((chain, i) => (
            <Bar key={chain} dataKey={`${chain}_promo`} fill="var(--green)" opacity={0.7} stackId={chain} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

type ProductPriceMode = "regular" | "promo" | "both";

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

  if (!priced.length) {
    return (
      <div className="rounded-md border bg-background p-4">
        <div className="mb-3 text-sm font-medium">Price history by chain</div>
        <div className="flex min-h-40 items-center justify-center text-sm text-muted-foreground">No prices to chart.</div>
      </div>
    );
  }

  const dates = Array.from(new Set(filtered.map((point) => compactDate(point.business_date)))).sort();
  const data = dates.map((date) => {
    const row: Record<string, string | number | null> = { date };
    chains.forEach((chain) => {
      const point = filtered.find((item) => item.chain === chain && compactDate(item.business_date) === date);
      row[`${chain}__regular`] = point?.reference_price_amount ?? null;
      row[`${chain}__promo`] = point?.promo_detected ? point?.promo_price_amount ?? null : null;
    });
    return row;
  });
  return (
    <div className="rounded-[10px] border border-border-2 bg-card px-4 py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-[13px] font-medium">Price timeline</div>
          <div className="mt-1 text-[11px] text-ink-muted">Regular and promotional prices across chains.</div>
        </div>
        <div className="text-xs text-muted-foreground">{dates.length} days · {chains.length} chains</div>
      </div>
      <ResponsiveContainer width="100%" height={360}>
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="0" stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--ink-muted)" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis domain={[0, "auto"]} tick={{ fontSize: 10, fill: "var(--ink-muted)" }} axisLine={false} tickLine={false} tickFormatter={formatTooltip} width={72} />
          <Tooltip
            formatter={formatTooltip}
            contentStyle={{
              background: "var(--surface)",
              border: "0.5px solid var(--border-2)",
              borderRadius: 8,
              boxShadow: "none",
              fontSize: 12,
            }}
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
                  connectNulls
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
        </LineChart>
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
