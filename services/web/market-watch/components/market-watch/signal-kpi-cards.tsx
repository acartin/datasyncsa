import { AlertTriangle, Bell, Gauge, Percent, Repeat2, Tags } from "lucide-react";
import { KpiCard } from "@/components/market-watch/kpi-card";
import { SignalKpis } from "@/lib/pricing-types";

export function SignalKpiCards({ kpis }: { kpis: SignalKpis }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
      <KpiCard icon={Gauge} value={kpis.total_signals ?? 0} label="Total signals" />
      <KpiCard icon={AlertTriangle} value={kpis.high_severity_signals ?? 0} label="High severity" />
      <KpiCard icon={Bell} value={kpis.new_signals ?? 0} label="New signals" />
      <KpiCard icon={Repeat2} value={kpis.active_repeated_signals ?? 0} label="Active/repeated" />
      <KpiCard icon={Tags} value={kpis.promo_signals ?? 0} label="Promo signals" />
      <KpiCard icon={Percent} value={kpis.price_gap_signals ?? 0} label="Price gap" />
    </div>
  );
}
