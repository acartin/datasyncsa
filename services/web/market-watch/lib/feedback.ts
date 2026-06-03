export type Feedback = {
  type: "success" | "warning" | "error" | "info";
  message: string;
};

export function feedbackFromSearchParams(params?: { feedback?: string; message?: string }): Feedback | null {
  const type = params?.feedback;
  if (type !== "success" && type !== "warning" && type !== "error" && type !== "info") return null;

  return {
    type,
    message: params?.message?.trim() || "Operation processed."
  };
}

export function friendlyApiError(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "The operation could not be completed.";
  const detail = (payload as { detail?: unknown }).detail;

  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { loc?: unknown[]; msg?: string; ctx?: { min_length?: number } } | undefined;
    const field = Array.isArray(first?.loc) ? String(first?.loc.at(-1) ?? "field") : "field";
    if (first?.ctx?.min_length) {
      return `The ${field} field must have at least ${first.ctx.min_length} characters.`;
    }
    if (first?.msg) return `${field}: ${first.msg}`;
  }

  return "The operation could not be completed. Review the fields and try again.";
}

export function feedbackQuery(type: Feedback["type"], message: string) {
  const searchParams = new URLSearchParams({ feedback: type, message });
  return searchParams.toString();
}
