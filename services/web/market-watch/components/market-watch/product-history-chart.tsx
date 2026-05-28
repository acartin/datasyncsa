"use client";

import { IntradayProductHistoryPoint } from "@/lib/pricing-types";
import { IntradayProductDailyPoint } from "@/lib/pricing-types";
import { IntradayProductPricePoint } from "@/lib/pricing-types";

function currency(value: number) {
  return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
}

function timeLabel(value: string) {
  return value.includes("T") ? value.slice(11, 16) : value.slice(11, 16) || value;
}

function compactDate(value: string) {
  return value.slice(5);
}

function uniqueSorted<T>(values: T[]) {
  return Array.from(new Set(values)).sort();
}

function chartScale(values: number[]) {
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const rawSpan = Math.max(rawMax - rawMin, 1);
  const padding = rawSpan * 0.12;
  const min = Math.max(0, rawMin - padding);
  const max = rawMax + padding;
  return { min, max, span: Math.max(max - min, 1), rawMin, rawMax };
}

export function ProductHistoryChart({ history }: { history: IntradayProductHistoryPoint[] }) {
  const priced = history.filter((item) => typeof item.average_price === "number");
  const chains = Array.from(new Set(priced.map((item) => item.chain))).slice(0, 4);
  const values = priced.map((item) => item.average_price as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const width = 720;
  const height = 240;
  const padding = 28;
  const colors = ["hsl(var(--primary))", "hsl(var(--destructive))", "hsl(var(--accent-foreground))", "hsl(var(--secondary-foreground))"];

  if (!priced.length) {
    return <div className="flex min-h-48 items-center justify-center text-sm text-muted-foreground">Sin precio historico para graficar.</div>;
  }

  const byChain = chains.map((chain, chainIndex) => {
    const points = priced.filter((item) => item.chain === chain);
    const path = points
      .map((item, index) => {
        const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
        const y = height - padding - (((item.average_price as number) - min) / span) * (height - padding * 2);
        return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
    return { chain, path, color: colors[chainIndex % colors.length], points };
  });

  return (
    <div className="overflow-x-auto">
      <div className="mb-3 flex flex-wrap gap-3 text-xs">
        {byChain.map((item) => (
          <div key={item.chain} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
            <span>{item.chain}</span>
          </div>
        ))}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-64 min-w-[680px] rounded-md border bg-background">
        <line x1={padding} x2={width - padding} y1={height - padding} y2={height - padding} stroke="hsl(var(--border))" />
        <line x1={padding} x2={padding} y1={padding} y2={height - padding} stroke="hsl(var(--border))" />
        <text x={padding} y={18} className="fill-muted-foreground text-[11px]">
          {currency(max)}
        </text>
        <text x={padding} y={height - 8} className="fill-muted-foreground text-[11px]">
          {currency(min)}
        </text>
        {byChain.map((item) => (
          <g key={item.chain}>
            <path d={item.path} fill="none" stroke={item.color} strokeWidth="2.5" />
            {item.points.map((point, index) => {
              const x = padding + (index / Math.max(item.points.length - 1, 1)) * (width - padding * 2);
              const y = height - padding - (((point.average_price as number) - min) / span) * (height - padding * 2);
              return <circle key={`${item.chain}-${point.captured_at_cr}`} cx={x} cy={y} r="3" fill={item.color} />;
            })}
          </g>
        ))}
        {byChain[0]?.points.map((point, index) => {
          const x = padding + (index / Math.max(byChain[0].points.length - 1, 1)) * (width - padding * 2);
          return (
            <text key={point.captured_at_cr} x={x} y={height - 10} textAnchor="middle" className="fill-muted-foreground text-[10px]">
              {index % 2 === 0 ? timeLabel(point.captured_at_cr) : ""}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

export function ProductDailyHistoryChart({ history }: { history: IntradayProductDailyPoint[] }) {
  const priced = history.filter((item) => typeof item.average_price === "number");
  const chains = Array.from(new Set(priced.map((item) => item.chain))).slice(0, 4);
  const dates = uniqueSorted(priced.map((item) => item.business_date));
  const values = priced.map((item) => item.average_price as number);
  const scale = chartScale(values);
  const width = 720;
  const height = 240;
  const padding = { top: 22, right: 18, bottom: 34, left: 72 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const colors = ["hsl(var(--primary))", "hsl(var(--destructive))", "hsl(var(--accent-foreground))", "hsl(var(--secondary-foreground))"];

  if (!priced.length) {
    return <div className="flex min-h-48 items-center justify-center text-sm text-muted-foreground">Sin histórico diario para graficar.</div>;
  }

  const yFor = (value: number) => padding.top + ((scale.max - value) / scale.span) * plotHeight;
  const xFor = (index: number) => padding.left + (index / Math.max(dates.length - 1, 1)) * plotWidth;
  const ticks = [scale.rawMax, scale.rawMin];

  const byChain = chains.map((chain, chainIndex) => {
    const points: IntradayProductDailyPoint[] = [];
    dates.forEach((date) => {
      const point = priced.find((item) => item.chain === chain && item.business_date === date);
      if (point && typeof point.average_price === "number") points.push(point);
    });
    const path = points
      .map((item) => {
        const dateIndex = dates.indexOf(item.business_date);
        const x = xFor(dateIndex);
        const y = yFor(item.average_price as number);
        return `${dateIndex === dates.indexOf(points[0].business_date) ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
    return { chain, path, color: colors[chainIndex % colors.length], points };
  });

  return (
    <div className="overflow-x-auto">
      <div className="mb-3 flex flex-wrap gap-3 text-xs">
        {byChain.map((item) => (
          <div key={item.chain} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
            <span>{item.chain}</span>
          </div>
        ))}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-64 min-w-[680px] rounded-md border bg-background">
        <line x1={padding.left} x2={width - padding.right} y1={height - padding.bottom} y2={height - padding.bottom} stroke="hsl(var(--border))" />
        <line x1={padding.left} x2={padding.left} y1={padding.top} y2={height - padding.bottom} stroke="hsl(var(--border))" />
        {ticks.map((tick) => {
          const y = yFor(tick);
          return (
            <g key={tick}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="hsl(var(--border))" strokeDasharray="3 4" opacity="0.7" />
              <text x={padding.left - 8} y={y + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">
                {currency(tick)}
              </text>
            </g>
          );
        })}
        {byChain.map((item) => (
          <g key={item.chain}>
            <path d={item.path} fill="none" stroke={item.color} strokeWidth="2.5" />
            {item.points.map((point) => {
              const dateIndex = dates.indexOf(point.business_date);
              const x = xFor(dateIndex);
              const y = yFor(point.average_price as number);
              return <circle key={`${item.chain}-${point.business_date}`} cx={x} cy={y} r="3" fill={item.color} />;
            })}
          </g>
        ))}
        {dates.map((date, index) => {
          const x = xFor(index);
          return (
            <text key={date} x={x} y={height - 12} textAnchor="middle" className="fill-muted-foreground text-[10px]">
              {index % 2 === 0 || dates.length <= 12 ? compactDate(date) : ""}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

export function ProductPromoTimelineChart({ history }: { history: IntradayProductHistoryPoint[] }) {
  const points = history
    .filter((item) => item.captured_at_cr)
    .sort((a, b) => a.captured_at_cr.localeCompare(b.captured_at_cr));
  const chains = Array.from(new Set(points.map((item) => item.chain))).slice(0, 5);
  const captures = uniqueSorted(points.map((item) => item.captured_at_cr));
  const width = 720;
  const rowHeight = 42;
  const padding = { top: 34, right: 24, bottom: 30, left: 92 };
  const height = padding.top + chains.length * rowHeight + padding.bottom;
  const plotWidth = width - padding.left - padding.right;

  if (!points.length) {
    return <div className="flex min-h-32 items-center justify-center text-sm text-muted-foreground">Sin capturas intradía para graficar.</div>;
  }

  const xFor = (index: number) => padding.left + (index / Math.max(captures.length - 1, 1)) * plotWidth;

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
      <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[680px] rounded-md border bg-background" style={{ height }}>
        <line x1={padding.left} x2={width - padding.right} y1={padding.top - 16} y2={padding.top - 16} stroke="hsl(var(--border))" />
        {chains.map((chain, chainIndex) => {
          const y = padding.top + chainIndex * rowHeight + rowHeight / 2;
          const chainPoints = points.filter((item) => item.chain === chain);
          return (
            <g key={chain}>
              <text x={padding.left - 12} y={y + 4} textAnchor="end" className="fill-foreground text-[11px]">
                {chain}
              </text>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="hsl(var(--border))" />
              {chainPoints.map((point) => {
                const index = captures.indexOf(point.captured_at_cr);
                const x = xFor(index);
                const promo = Boolean(point.promo_detected);
                return (
                  <g key={`${point.chain}-${point.captured_at_cr}`}>
                    <circle
                      cx={x}
                      cy={y}
                      r={promo ? 6 : 5}
                      fill={promo ? "rgb(16 185 129)" : "hsl(var(--background))"}
                      stroke={promo ? "rgb(5 150 105)" : "hsl(var(--muted-foreground))"}
                      strokeWidth="1.5"
                    />
                    {typeof point.average_price === "number" ? (
                      <text x={x} y={y - 12} textAnchor="middle" className="fill-muted-foreground text-[9px]">
                        {index === 0 || index === captures.length - 1 || promo ? currency(point.average_price) : ""}
                      </text>
                    ) : null}
                  </g>
                );
              })}
            </g>
          );
        })}
        {captures.map((capture, index) => {
          const x = xFor(index);
          return (
            <g key={capture}>
              <line x1={x} x2={x} y1={padding.top - 16} y2={height - padding.bottom + 4} stroke="hsl(var(--border))" opacity={index % 2 === 0 ? 0.5 : 0.2} />
              <text x={x} y={height - 10} textAnchor="middle" className="fill-muted-foreground text-[10px]">
                {index % 2 === 0 || captures.length <= 8 ? timeLabel(capture) : ""}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function lineSegments({
  points,
  valueKey,
  xFor,
  yFor
}: {
  points: IntradayProductPricePoint[];
  valueKey: "reference_price_amount" | "promo_price_amount";
  xFor: (index: number) => number;
  yFor: (value: number) => number;
}) {
  const segments: string[] = [];
  let currentSegment: string[] = [];

  points.forEach((point, index) => {
    const value = point[valueKey];
    if (typeof value !== "number") {
      if (currentSegment.length) {
        segments.push(currentSegment.join(" "));
        currentSegment = [];
      }
      return;
    }
    const x = xFor(index);
    const y = yFor(value);
    currentSegment.push(`${currentSegment.length === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`);
  });
  if (currentSegment.length) segments.push(currentSegment.join(" "));

  return segments;
}

function CombinedPriceChart({ points }: { points: IntradayProductPricePoint[] }) {
  const priced = points.filter((point) => typeof point.reference_price_amount === "number" || typeof point.promo_price_amount === "number");
  const promoPoints = points.filter((point) => typeof point.promo_price_amount === "number");
  const width = 820;
  const height = 250;
  const padding = { top: 24, right: 18, bottom: 38, left: 72 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  if (!priced.length) {
    return (
      <div className="rounded-md border bg-background p-4">
        <div className="mb-3 text-sm font-medium">Precio normal vs promocional</div>
        <div className="flex min-h-40 items-center justify-center text-sm text-muted-foreground">Sin precios para graficar.</div>
      </div>
    );
  }

  const values = priced.flatMap((point) =>
    [point.reference_price_amount, point.promo_price_amount].filter((value): value is number => typeof value === "number")
  );
  const scale = chartScale(values);
  const yFor = (value: number) => padding.top + ((scale.max - value) / scale.span) * plotHeight;
  const xFor = (index: number) => padding.left + (index / Math.max(points.length - 1, 1)) * plotWidth;
  const normalColor = "hsl(var(--primary))";
  const promoColor = "hsl(var(--destructive))";
  const normalSegments = lineSegments({ points, valueKey: "reference_price_amount", xFor, yFor });
  const promoSegments = lineSegments({ points, valueKey: "promo_price_amount", xFor, yFor });
  const firstNormalIndex = points.findIndex((point) => typeof point.reference_price_amount === "number");
  const lastNormalIndex = points.findLastIndex((point) => typeof point.reference_price_amount === "number");
  const firstPromoIndex = points.findIndex((point) => typeof point.promo_price_amount === "number");
  const lastPromoIndex = points.findLastIndex((point) => typeof point.promo_price_amount === "number");

  return (
    <div className="rounded-md border bg-background p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium">Precio normal vs promocional</div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: normalColor }} />
            Normal
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: promoColor }} />
            Promocional
          </span>
          <span>Últimas {points.length} mediciones</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-64 min-w-[760px]">
        <line x1={padding.left} x2={width - padding.right} y1={height - padding.bottom} y2={height - padding.bottom} stroke="hsl(var(--border))" />
        <line x1={padding.left} x2={padding.left} y1={padding.top} y2={height - padding.bottom} stroke="hsl(var(--border))" />
        {[scale.rawMax, scale.rawMin].map((tick) => {
          const y = yFor(tick);
          return (
            <g key={tick}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="hsl(var(--border))" strokeDasharray="3 4" />
              <text x={padding.left - 8} y={y + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">
                {currency(tick)}
              </text>
            </g>
          );
        })}
        {normalSegments.map((path, index) => (
          <path key={`normal-segment-${index}`} d={path} fill="none" stroke={normalColor} strokeWidth="2.5" />
        ))}
        {promoSegments.map((path, index) => (
          <path key={`promo-segment-${index}`} d={path} fill="none" stroke={promoColor} strokeWidth="2.5" />
        ))}
        {points.map((point, index) => {
          const x = xFor(index);
          const normalValue = point.reference_price_amount;
          if (typeof normalValue !== "number") return null;
          const y = yFor(normalValue);
          return (
            <g key={`normal-${point.captured_at_cr}-${index}`}>
              <circle cx={x} cy={y} r="3" fill={normalColor} />
              {(index === firstNormalIndex || index === lastNormalIndex) && (
                <text x={x} y={y - 8} textAnchor="middle" className="fill-muted-foreground text-[10px]">
                  {currency(normalValue)}
                </text>
              )}
            </g>
          );
        })}
        {points.map((point, index) => {
          const x = xFor(index);
          const promoValue = point.promo_price_amount;
          if (typeof promoValue !== "number") return null;
          const y = yFor(promoValue);
          return (
            <g key={`promo-${point.captured_at_cr}-${index}`}>
              <circle cx={x} cy={y} r="3" fill={promoColor} />
              {(index === firstPromoIndex || index === lastPromoIndex) && (
                <text x={x} y={y + 16} textAnchor="middle" className="fill-muted-foreground text-[10px]">
                  {currency(promoValue)}
                </text>
              )}
            </g>
          );
        })}
        {promoPoints.map((point, index) => {
          const pointIndex = points.indexOf(point);
          const x = xFor(pointIndex);
          return (
            <line
              key={`promo-marker-${point.captured_at_cr}-${index}`}
              x1={x}
              x2={x}
              y1={padding.top}
              y2={height - padding.bottom}
              stroke={promoColor}
              strokeDasharray="2 6"
              opacity={0.15}
            />
          );
        })}
        {points.map((point, index) => {
          const x = xFor(index);
          return (
            <text key={`${point.captured_at_cr}-${index}`} x={x} y={height - 12} textAnchor="middle" className="fill-muted-foreground text-[10px]">
              {index % 5 === 0 || index === points.length - 1 ? compactDate(point.business_date) : ""}
            </text>
          );
        })}
      </svg>
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
