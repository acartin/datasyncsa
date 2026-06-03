import { IntradayRadarEvent } from "@/lib/pricing-types";

type EventPresentationConfig = {
  show_header_metrics?: boolean;
  change_visual?: "market_direction" | "semantic";
  value_display_mode?: "promo_state" | "default";
  show_change_value?: boolean;
};

function eventConfig(event: IntradayRadarEvent | null | undefined): EventPresentationConfig {
  return (event?.presentation?.config as EventPresentationConfig | undefined) ?? {};
}

export function showHeaderMetrics(event: IntradayRadarEvent | null | undefined): boolean {
  if (!event) return false;
  return eventConfig(event).show_header_metrics !== false;
}

export function changeDelta(event: IntradayRadarEvent | null | undefined): number | null {
  if (!event || typeof event.previous_value !== "number" || typeof event.current_value !== "number") return null;
  return event.current_value - event.previous_value;
}

export function changeVisualMode(event: IntradayRadarEvent | null | undefined): "market_direction" | "semantic" {
  return eventConfig(event).change_visual === "market_direction" ? "market_direction" : "semantic";
}

export function changeIndicator(event: IntradayRadarEvent | null | undefined): "up" | "down" | "flat" | null {
  if (changeVisualMode(event) !== "market_direction") return null;
  const delta = changeDelta(event);
  if (delta == null) return null;
  if (delta > 0) return "up";
  if (delta < 0) return "down";
  return "flat";
}

export function changeToneClass(event: IntradayRadarEvent | null | undefined): string {
  if (!event) return "text-foreground";

  const indicator = changeIndicator(event);
  if (indicator === "up") return "text-semantic-green";
  if (indicator === "down") return "text-semantic-red";
  if (indicator === "flat") return "text-ink-secondary";

  switch (event.presentation?.direction_semantics) {
    case "positive_good":
    case "negative_good":
      return "text-semantic-green";
    case "positive_bad":
    case "negative_bad":
      return "text-semantic-red";
    default:
      return "text-foreground";
  }
}

export function formatEventValue(event: IntradayRadarEvent | null | undefined, value: number | null, slot: "previous" | "current"): string {
  if (!event || value == null) return "-";

  const config = eventConfig(event);
  if (config.value_display_mode === "promo_state") {
    const labels = event.presentation?.metric_labels;
    if (value >= 100) return slot === "previous" ? labels?.previous ?? "With promo" : labels?.current ?? "With promo";
    if (value <= 0) return slot === "previous" ? labels?.previous ?? "No promo" : labels?.current ?? "No promo";
  }

  if (event.presentation?.value_format === "percent" || event.event_area === "promotion") {
    return `${value.toFixed(1)}%`;
  }

  if (event.presentation?.value_format === "currency" || event.event_area === "price") {
    return new Intl.NumberFormat("es-CR", { style: "currency", currency: "CRC", maximumFractionDigits: 0 }).format(value);
  }

  return String(value);
}

export function showChangeValue(event: IntradayRadarEvent | null | undefined): boolean {
  if (!event) return false;
  return eventConfig(event).show_change_value !== false;
}
