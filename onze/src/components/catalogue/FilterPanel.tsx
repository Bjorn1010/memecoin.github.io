"use client";

import { Check } from "lucide-react";
import type { Filters } from "@/lib/catalogue";
import { cn } from "@/lib/utils";

/* One panel, rendered in a desktop sidebar and inside the mobile bottom sheet.
 * Facet counts come from the parent so both instances stay in step. */

export interface FacetGroup {
  key: keyof Filters;
  label: string;
  options: { value: string; label: string }[];
  counts: Record<string, number>;
}

function Row({
  checked,
  label,
  count,
  onToggle,
}: {
  checked: boolean;
  label: string;
  count: number;
  onToggle: () => void;
}) {
  const disabled = count === 0 && !checked;
  return (
    <label
      className={cn(
        "flex cursor-pointer items-center gap-3 py-2 text-sm transition-colors",
        disabled ? "cursor-not-allowed text-steel-500" : "text-steel-300 hover:text-ink",
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        disabled={disabled}
        className="sr-only"
      />
      <span
        aria-hidden
        className={cn(
          "grid h-4 w-4 shrink-0 place-items-center rounded-xs border transition-colors",
          checked ? "border-volt bg-volt text-on-volt" : "border-ink/25",
        )}
      >
        {checked && <Check size={11} strokeWidth={3} />}
      </span>
      <span className="flex-1 truncate">{label}</span>
      <span className="tabular text-xs text-steel-500">{count}</span>
    </label>
  );
}

export function FilterPanel({
  filters,
  groups,
  priceMax,
  onToggle,
  onSet,
}: {
  filters: Filters;
  groups: FacetGroup[];
  priceMax: number;
  onToggle: (key: keyof Filters, value: string) => void;
  onSet: <K extends keyof Filters>(key: K, value: Filters[K]) => void;
}) {
  return (
    <div className="space-y-7">
      {/* Quick toggles first: these are the two filters people actually reach
          for, and burying them under six accordions is the usual mistake. */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onSet("promo", !filters.promo)}
          aria-pressed={filters.promo}
          className={cn(
            "label-mono rounded-full border px-4 py-2 transition-colors",
            filters.promo
              ? "border-sale bg-sale/15 text-sale"
              : "border-ink/15 text-steel-300 hover:border-ink/35",
          )}
        >
          En promo
        </button>
        <button
          type="button"
          onClick={() => onSet("enStock", !filters.enStock)}
          aria-pressed={filters.enStock}
          className={cn(
            "label-mono rounded-full border px-4 py-2 transition-colors",
            filters.enStock
              ? "border-volt bg-volt/15 text-volt"
              : "border-ink/15 text-steel-300 hover:border-ink/35",
          )}
        >
          En stock
        </button>
      </div>

      {groups.map((group) => {
        const selected = (filters[group.key] as string[]) ?? [];
        return (
          <fieldset key={String(group.key)} className="border-t border-ink/8 pt-5">
            <legend className="label-mono mb-2 text-steel-500">{group.label}</legend>
            {/* Long facets scroll rather than pushing everything else off-screen. */}
            <div
              className={cn(
                "no-scrollbar",
                group.options.length > 9 && "max-h-56 overflow-y-auto",
              )}
            >
              {group.options.map((o) => (
                <Row
                  key={o.value}
                  label={o.label}
                  count={group.counts[o.value] ?? 0}
                  checked={selected.includes(o.value)}
                  onToggle={() => onToggle(group.key, o.value)}
                />
              ))}
            </div>
          </fieldset>
        );
      })}

      <fieldset className="border-t border-ink/8 pt-5">
        <legend className="label-mono mb-4 text-steel-500">Prix maximum</legend>
        <input
          type="range"
          min={20}
          max={priceMax}
          step={5}
          value={filters.prixMax ?? priceMax}
          onChange={(e) => {
            const v = Number(e.target.value);
            onSet("prixMax", v >= priceMax ? null : v);
          }}
          aria-label="Prix maximum"
          className="w-full accent-[#0a9c4a]"
        />
        <p className="tabular mt-2 text-sm text-steel-300">
          Jusqu&apos;à {filters.prixMax ?? priceMax}.00 CHF
        </p>
      </fieldset>
    </div>
  );
}
