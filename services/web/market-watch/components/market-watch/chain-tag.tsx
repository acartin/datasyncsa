import { cn } from "@/lib/utils";

const chainStyles: Record<string, { background: string; color: string }> = {
  walmart: { background: "var(--chain-walmart-bg)", color: "var(--chain-walmart-text)" },
  "wal-mart": { background: "var(--chain-walmart-bg)", color: "var(--chain-walmart-text)" },
  "wal-mart fail": { background: "var(--chain-walmart-bg)", color: "var(--chain-walmart-text)" },
  "maxi pali": { background: "var(--chain-maxi-bg)", color: "var(--chain-maxi-text)" },
  "maxi palí": { background: "var(--chain-maxi-bg)", color: "var(--chain-maxi-text)" },
  "mas x menos": { background: "var(--chain-maximos-bg)", color: "var(--chain-maximos-text)" },
  "más x menos": { background: "var(--chain-maximos-bg)", color: "var(--chain-maximos-text)" },
  megasuper: { background: "var(--chain-mega-bg)", color: "var(--chain-mega-text)" },
};

function normalizeChain(value: string) {
  return value.trim().toLowerCase();
}

export function ChainTag({ chain, className }: { chain?: string | null; className?: string }) {
  if (!chain) return null;
  const style = chainStyles[normalizeChain(chain)] ?? {
    background: "var(--surface-2)",
    color: "var(--ink-secondary)",
  };

  return (
    <span
      className={cn("inline-flex items-center whitespace-nowrap rounded px-2 py-0.5 text-[11px] font-medium", className)}
      style={style}
    >
      {chain}
    </span>
  );
}
