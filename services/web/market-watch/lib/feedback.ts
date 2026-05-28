export type Feedback = {
  type: "success" | "warning" | "error" | "info";
  message: string;
};

export function feedbackFromSearchParams(params?: { feedback?: string; message?: string }): Feedback | null {
  const type = params?.feedback;
  if (type !== "success" && type !== "warning" && type !== "error" && type !== "info") return null;

  return {
    type,
    message: params?.message?.trim() || "Operacion procesada."
  };
}

export function friendlyApiError(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "No se pudo completar la operacion.";
  const detail = (payload as { detail?: unknown }).detail;

  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { loc?: unknown[]; msg?: string; ctx?: { min_length?: number } } | undefined;
    const field = Array.isArray(first?.loc) ? String(first?.loc.at(-1) ?? "campo") : "campo";
    if (first?.ctx?.min_length) {
      return `El campo ${field} debe tener al menos ${first.ctx.min_length} caracteres.`;
    }
    if (first?.msg) return `${field}: ${first.msg}`;
  }

  return "No se pudo completar la operacion. Revisa los campos e intenta de nuevo.";
}

export function feedbackQuery(type: Feedback["type"], message: string) {
  const searchParams = new URLSearchParams({ feedback: type, message });
  return searchParams.toString();
}
