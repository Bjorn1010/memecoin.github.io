"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { SlidersHorizontal, X } from "lucide-react";
import type { Category, Product } from "@/lib/types";
import {
  applyFilters,
  countActive,
  emptyFilters,
  facetCounts,
  SORT_LABELS,
  sortProducts,
  type Filters,
  type SortKey,
} from "@/lib/catalogue";
import { FilterPanel, type FacetGroup } from "@/components/catalogue/FilterPanel";
import { ProductGrid, ProductGridSkeleton } from "@/components/products/ProductGrid";
import { Button } from "@/components/ui/Button";
import { clubs, countries, leagues } from "@/lib/data/teams";
import { priceBounds, seasons } from "@/lib/data/products";
import { scrim, slideUpSheet, transition } from "@/lib/motion";
import { cn } from "@/lib/utils";

const PAGE = 12;

const KIT_OPTIONS = [
  { value: "domicile", label: "Domicile" },
  { value: "exterieur", label: "Extérieur" },
  { value: "third", label: "Third" },
  { value: "retro", label: "Rétro" },
];

const CATEGORY_OPTIONS: { value: Category; label: string }[] = [
  { value: "maillots", label: "Maillots" },
  { value: "kits-enfants", label: "Kits enfants" },
  { value: "retros", label: "Rétros" },
  { value: "editions-speciales", label: "Éditions spéciales" },
  { value: "survetements", label: "Survêtements" },
  { value: "vestes", label: "Vestes & pulls" },
];

export function CatalogueView({
  products,
  title,
  eyebrow,
  initialFilters,
  lockedFacets = [],
}: {
  products: Product[];
  title: string;
  eyebrow: string;
  initialFilters?: Partial<Filters>;
  /** Facets the page fixes itself (a collection page locks its category). */
  lockedFacets?: (keyof Filters)[];
}) {
  const [filters, setFilters] = useState<Filters>({ ...emptyFilters, ...initialFilters });
  const [sort, setSort] = useState<SortKey>("pertinence");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [visible, setVisible] = useState(PAGE);
  const [pending, setPending] = useState(false);

  /* Deferring keeps the filter checkboxes responsive while a large grid
     re-renders behind them. */
  const deferred = useDeferredValue(filters);

  const results = useMemo(
    () => sortProducts(applyFilters(products, deferred), sort),
    [products, deferred, sort],
  );

  /* A short pending state on filter change: without it the grid swaps
     instantly and the change is easy to miss. The skeleton is the feedback. */
  useEffect(() => {
    setPending(true);
    setVisible(PAGE);
    const id = window.setTimeout(() => setPending(false), 220);
    return () => window.clearTimeout(id);
  }, [deferred, sort]);

  useEffect(() => {
    document.body.style.overflow = sheetOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [sheetOpen]);

  const groups: FacetGroup[] = useMemo(() => {
    const all: FacetGroup[] = [
      {
        key: "category",
        label: "Catégorie",
        options: CATEGORY_OPTIONS,
        counts: facetCounts(products, deferred, "category", CATEGORY_OPTIONS.map((o) => o.value)),
      },
      {
        key: "league",
        label: "Championnat",
        options: leagues.map((l) => ({ value: l, label: l })),
        counts: facetCounts(products, deferred, "league", [...leagues]),
      },
      {
        key: "club",
        label: "Club",
        options: clubs.map((c) => ({ value: c.slug, label: c.name })),
        counts: facetCounts(products, deferred, "club", clubs.map((c) => c.slug)),
      },
      {
        key: "pays",
        label: "Sélection",
        options: countries.map((c) => ({ value: c.slug, label: c.name })),
        counts: facetCounts(products, deferred, "pays", countries.map((c) => c.slug)),
      },
      {
        key: "kit",
        label: "Type de kit",
        options: KIT_OPTIONS,
        counts: facetCounts(products, deferred, "kit", KIT_OPTIONS.map((o) => o.value)),
      },
      {
        key: "saison",
        label: "Saison",
        options: seasons.map((s) => ({ value: s, label: s })),
        counts: facetCounts(products, deferred, "saison", seasons),
      },
      {
        key: "taille",
        label: "Taille",
        options: ["S", "M", "L", "XL", "XXL"].map((s) => ({ value: s, label: s })),
        counts: facetCounts(products, deferred, "taille", ["S", "M", "L", "XL", "XXL"]),
      },
    ];
    return all.filter((g) => !lockedFacets.includes(g.key));
  }, [products, deferred, lockedFacets]);

  function toggle(key: keyof Filters, value: string) {
    setFilters((prev) => {
      const list = prev[key] as string[];
      return {
        ...prev,
        [key]: list.includes(value) ? list.filter((v) => v !== value) : [...list, value],
      };
    });
  }

  function set<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  const active = countActive(filters);
  const shown = results.slice(0, visible);

  return (
    <div className="mx-auto max-w-[1600px] px-5 pt-32 lg:px-10">
      <header className="mb-10">
        <p className="label-mono mb-4 flex items-center gap-3 text-volt">
          <span className="inline-block h-px w-8 bg-volt" />
          {eyebrow}
        </p>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h1 className="font-display text-display text-white">{title}</h1>
          <p className="scoreboard text-2xl text-steel-400">
            {results.length}
            <span className="ml-2 font-sans text-xs font-normal uppercase tracking-[0.16em] text-steel-600">
              {results.length > 1 ? "références" : "référence"}
            </span>
          </p>
        </div>
      </header>

      <div className="grid gap-10 lg:grid-cols-[248px_1fr]">
        {/* Desktop sidebar */}
        <aside className="hidden lg:block">
          <div className="sticky top-28 max-h-[calc(100vh-8rem)] overflow-y-auto pr-2 no-scrollbar">
            <div className="mb-5 flex items-center justify-between">
              <p className="label-mono text-white">Filtres</p>
              {active > 0 && (
                <button
                  type="button"
                  onClick={() => setFilters({ ...emptyFilters, ...initialFilters })}
                  className="label-mono text-steel-500 transition-colors hover:text-sale"
                >
                  Effacer ({active})
                </button>
              )}
            </div>
            <FilterPanel
              filters={filters}
              groups={groups}
              priceMax={priceBounds.max}
              onToggle={toggle}
              onSet={set}
            />
          </div>
        </aside>

        <div>
          {/* Toolbar */}
          <div className="mb-8 flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSheetOpen(true)}
              className="label-mono flex items-center gap-2 rounded-sm border border-white/15 px-4 py-2.5 text-steel-200 transition-colors hover:border-white/35 lg:hidden"
            >
              <SlidersHorizontal size={14} />
              Filtres
              {active > 0 && (
                <span className="tabular grid h-5 min-w-5 place-items-center rounded-full bg-volt px-1 text-[10px] font-bold text-void">
                  {active}
                </span>
              )}
            </button>

            <label className="ml-auto flex items-center gap-2">
              <span className="label-mono hidden text-steel-500 sm:inline">Trier par</span>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                className="label-mono cursor-pointer rounded-sm border border-white/15 bg-surface px-3 py-2.5 text-steel-200 outline-none transition-colors hover:border-white/35 focus:border-volt"
              >
                {Object.entries(SORT_LABELS).map(([k, v]) => (
                  <option key={k} value={k} className="bg-surface">
                    {v}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* Results */}
          {pending ? (
            <ProductGridSkeleton count={8} />
          ) : results.length === 0 ? (
            <div className="pitch-lines flex flex-col items-center justify-center rounded-xl border border-white/8 bg-surface px-6 py-24 text-center">
              <p className="scoreboard relative text-5xl text-steel-700">0</p>
              <p className="relative mt-4 font-display text-xl uppercase text-white">
                Aucun résultat
              </p>
              <p className="relative mt-2 max-w-sm text-sm text-steel-400">
                Aucune référence ne correspond à cette combinaison de filtres.
              </p>
              <Button
                variant="outline"
                size="sm"
                className="relative mt-6"
                onClick={() => setFilters({ ...emptyFilters, ...initialFilters })}
              >
                Réinitialiser les filtres
              </Button>
            </div>
          ) : (
            <>
              <ProductGrid products={shown} columns={3} />
              {visible < results.length && (
                <div className="mt-16 flex flex-col items-center gap-4">
                  <p className="label-mono text-steel-500">
                    {shown.length} sur {results.length}
                  </p>
                  {/* A button, not infinite scroll: the footer stays reachable
                      and the back button returns you where you were. */}
                  <Button variant="outline" onClick={() => setVisible((v) => v + PAGE)}>
                    Afficher plus
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Mobile bottom sheet */}
      <AnimatePresence>
        {sheetOpen && (
          <>
            <motion.div
              variants={scrim}
              initial="hidden"
              animate="visible"
              exit="exit"
              onClick={() => setSheetOpen(false)}
              className="fixed inset-0 z-[88] bg-black/70 backdrop-blur-sm lg:hidden"
            />
            <motion.div
              variants={slideUpSheet}
              initial="hidden"
              animate="visible"
              exit="exit"
              role="dialog"
              aria-modal="true"
              aria-label="Filtres"
              className="fixed inset-x-0 bottom-0 z-[89] max-h-[85dvh] overflow-y-auto rounded-t-xl border-t border-white/12 bg-base lg:hidden"
            >
              {/* Grab handle — signals the sheet is dismissable by drag on
                  platforms where that is the expectation. */}
              <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/8 bg-base px-5 pb-4 pt-3">
                <div className="absolute left-1/2 top-1.5 h-1 w-9 -translate-x-1/2 rounded-full bg-white/20" />
                <p className="font-display text-lg uppercase text-white">Filtres</p>
                <button
                  type="button"
                  onClick={() => setSheetOpen(false)}
                  aria-label="Fermer les filtres"
                  className="grid h-9 w-9 place-items-center text-steel-400"
                >
                  <X size={20} />
                </button>
              </div>

              <div className="px-5 py-6">
                <FilterPanel
                  filters={filters}
                  groups={groups}
                  priceMax={priceBounds.max}
                  onToggle={toggle}
                  onSet={set}
                />
              </div>

              <div className="sticky bottom-0 flex gap-3 border-t border-white/8 bg-base px-5 py-4">
                <Button
                  variant="outline"
                  className={cn("flex-1", active === 0 && "opacity-50")}
                  onClick={() => setFilters({ ...emptyFilters, ...initialFilters })}
                >
                  Effacer
                </Button>
                <Button className="flex-[1.5]" onClick={() => setSheetOpen(false)}>
                  Voir {results.length} résultats
                </Button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
