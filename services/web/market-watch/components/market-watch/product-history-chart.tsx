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

const chartColors = ["hsl(var(--primary))", "hsl(var(--destructive))", "hsl(var(--accent-foreground))", "hsl(var(--secondary-foreground))"];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const formatTooltip: any = (value: number) => currency(value);

export function ProductHistoryChart({ history }: { history: IntradayProductHistoryPoint[] }) {
  const priced = history.filter((item) => typeof item.average_price === "number");
  const chains = Array.from(new Set(priced.map((item) => item.chain))).slice(0, 4);

  if (!priced.length) {
    return <div className="flex min-h-48 items-center justify-center text-sm text-muted-foreground">Sin precio historico para graficar.</div>;
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
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
          <XAxis dataKey="capture" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" interval="preserveStartEnd" />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" tickFormatter={formatTooltip} width={72} />
          <Tooltip formatter={formatTooltip} contentStyle={{ fontSize: 13 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {chains.map((chain, i) => (
            <Line key={chain} type="monotone" dataKey={chain} stroke={chartColors[i % chartColors.length]} strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
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
    return <div className="flex min-h-48 items-center justify-center text-sm text-muted-foreground">Sin historico diario para graficar.</div>;
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
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" interval="preserveStartEnd" />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" tickFormatter={formatTooltip} width={72} />
          <Tooltip formatter={formatTooltip} contentStyle={{ fontSize: 13 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {chains.map((chain, i) => (
            <Line key={chain} type="monotone" dataKey={chain} stroke={chartColors[i % chartColors.length]} strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
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
    return <div className="flex min-h-32 items-center justify-center text-sm text-muted-foreground">Sin capturas intradia para graficar.</div>;
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
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
          <span>Promo activa</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full border border-muted-foreground bg-background" />
          <span>Sin promo</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={chains.length * 50 + 40}>
        <ComposedChart data={data} margin={{ top: 8, right: 20, bottom: 8, left: 8 }} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="capture" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" width={60} />
          <Tooltip contentStyle={{ fontSize: 13 }} />
          {chains.map((chain, i) => (
            <Bar key={chain} dataKey={`${chain}_promo`} fill="rgb(16 185 129)" opacity={0.7} stackId={chain} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function CombinedPriceChart({ points }: { points: IntradayProductPricePoint[] }) {
  const priced = points.filter((p) => typeof p.reference_price_amount === "number" || typeof p.promo_price_amount === "number");

  if (!priced.length) {
    return (
      <div className="rounded-md border bg-background p-4">
        <div className="mb-3 text-sm font-medium">Precio normal vs promocional</div>
        <div className="flex min-h-40 items-center justify-center text-sm text-muted-foreground">Sin precios para graficar.</div>
      </div>
    );
  }

  const data = points.map((p, i) => ({
    index: i,
    date: compactDate(p.business_date),
    normal: p.reference_price_amount,
    promo: p.promo_price_amount,
    promo_active: p.promo_detected,
  }));

  return (
    <div className="rounded-md border bg-background p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium">Precio normal vs promocional</div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "hsl(var(--primary))" }} />
            Normal
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "hsl(var(--destructive))" }} />
            Promocional
          </span>
          <span>Ultimas {points.length} mediciones</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 20, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" interval="preserveStartEnd" />
          <YAxis domain={[0, "auto"]} tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" tickFormatter={formatTooltip} width={72} />
          <Tooltip formatter={formatTooltip} contentStyle={{ fontSize: 13 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="normal" stroke="hsl(var(--primary))" strokeWidth={2.5} dot={{ r: 3 }} name="Normal" connectNulls />
          <Line type="monotone" dataKey="promo" stroke="hsl(var(--destructive))" strokeWidth={2.5} dot={{ r: 3 }} name="Promocional" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ProductNormalPromoPriceCharts({ history }: { history: IntradayProductPricePoint[] }) {
  return (
    <div className="overflow-x-auto">
      <CombinedPriceChart points={history} />
    </div>
  );
}