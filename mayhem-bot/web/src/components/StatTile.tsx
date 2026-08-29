import type { ReactNode } from "react";

export function StatTile({
  label,
  value,
  sub,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "up" | "down";
  icon?: ReactNode;
}) {
  const valueColor = tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-white";

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-panel2/60 px-4 py-2.5">
      {icon && <div className="text-dim">{icon}</div>}
      <div className="min-w-0">
        <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
        <div className={`tabular font-mono text-lg font-semibold leading-tight ${valueColor}`}>{value}</div>
        {sub && <div className="text-[11px] text-dim">{sub}</div>}
      </div>
    </div>
  );
}
