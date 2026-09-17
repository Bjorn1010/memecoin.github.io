import { useState } from "react";
import { api } from "../lib/api";
import type { StrategyConfig } from "../lib/types";

function NumberField({
  label,
  value,
  onChange,
  step = 0.01,
  suffix,
  allowNull = false,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  step?: number;
  suffix?: string;
  allowNull?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-[11px] font-medium text-muted">
      <span className="flex items-center justify-between">
        {label}
        {allowNull && (
          <button
            type="button"
            onClick={() => onChange(value == null ? 0 : null)}
            className="text-[10px] font-semibold text-accent hover:text-accent/80"
          >
            {value == null ? "activer" : "désactiver"}
          </button>
        )}
      </span>
      <div className="flex items-center gap-1.5">
        <input
          type="number"
          step={step}
          disabled={allowNull && value == null}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
          className="w-full rounded-md border border-border bg-panel2 px-2.5 py-1.5 font-mono text-sm text-white outline-none transition-colors focus:border-accent disabled:opacity-40"
        />
        {suffix && <span className="shrink-0 text-[10px] text-dim">{suffix}</span>}
      </div>
    </label>
  );
}

export function StrategyEditor({ config, onClose }: { config: StrategyConfig; onClose: () => void }) {
  const [draft, setDraft] = useState<StrategyConfig>(config);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api.updateStrategy(draft);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl border border-borderLight bg-panel p-6 shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-1 flex items-start justify-between">
          <div>
            <h2 className="text-base font-bold text-white">{draft.name}</h2>
            <p className="mt-0.5 text-[12px] text-muted">{draft.description}</p>
          </div>
          <button onClick={onClose} className="text-dim transition-colors hover:text-white">
            ✕
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3.5">
          <NumberField
            label="Solde de départ"
            value={draft.startingBalanceSol}
            step={0.5}
            suffix="SOL"
            onChange={(v) => setDraft((d) => ({ ...d, startingBalanceSol: v ?? 0.1 }))}
          />
          <NumberField
            label="Taille par position"
            value={draft.positionSizeSol}
            step={0.05}
            suffix="SOL"
            onChange={(v) => setDraft((d) => ({ ...d, positionSizeSol: v ?? 0.05 }))}
          />
          <NumberField
            label="Take profit"
            value={draft.takeProfitPct}
            step={0.05}
            suffix="× (0.1 = +10%)"
            allowNull
            onChange={(v) => setDraft((d) => ({ ...d, takeProfitPct: v }))}
          />
          <NumberField
            label="Stop loss"
            value={draft.stopLossPct}
            step={0.05}
            suffix="× (0.1 = -10%)"
            allowNull
            onChange={(v) => setDraft((d) => ({ ...d, stopLossPct: v }))}
          />
          <NumberField
            label="Trailing stop"
            value={draft.trailingStopPct}
            step={0.05}
            suffix="× depuis le pic"
            allowNull
            onChange={(v) => setDraft((d) => ({ ...d, trailingStopPct: v }))}
          />
          <NumberField
            label="Durée max de hold"
            value={draft.maxHoldSeconds}
            step={30}
            suffix="sec"
            allowNull
            onChange={(v) => setDraft((d) => ({ ...d, maxHoldSeconds: v }))}
          />
          <NumberField
            label="Achat Mayhem min."
            value={draft.minMayhemBuySol}
            step={0.01}
            suffix="SOL"
            allowNull
            onChange={(v) => setDraft((d) => ({ ...d, minMayhemBuySol: v }))}
          />
          <NumberField
            label="Liquidité pool min."
            value={draft.minPoolLiquiditySol}
            step={1}
            suffix="SOL"
            allowNull
            onChange={(v) => setDraft((d) => ({ ...d, minPoolLiquiditySol: v }))}
          />
          <NumberField
            label="Positions max en //"
            value={draft.maxConcurrentPositions}
            step={1}
            onChange={(v) => setDraft((d) => ({ ...d, maxConcurrentPositions: v ?? 1 }))}
          />
          <NumberField
            label="Frais de priorité"
            value={draft.priorityFeeSol}
            step={0.001}
            suffix="SOL / trade"
            onChange={(v) => setDraft((d) => ({ ...d, priorityFeeSol: v ?? 0 }))}
          />
        </div>

        <label className="mt-4 flex items-center gap-2 rounded-lg border border-border bg-panel2/50 px-3 py-2.5 text-[12px] text-muted">
          <input
            type="checkbox"
            checked={draft.sellOnMayhemFullExit}
            onChange={(e) => setDraft((d) => ({ ...d, sellOnMayhemFullExit: e.target.checked }))}
            className="accent-accent"
          />
          Vendre tout si le wallet Mayhem liquide entièrement sa position (vault dump)
        </label>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted transition-colors hover:text-white"
          >
            Annuler
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {saving ? "…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
