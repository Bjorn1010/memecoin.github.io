"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { Search, X } from "lucide-react";
import { products } from "@/lib/data/products";
import { Jersey } from "@/components/ui/Jersey";
import { formatPrice } from "@/lib/utils";
import { transition } from "@/lib/motion";

/* Client-side search over the in-memory catalogue. Scores name, team and
 * season so "psg 26" and "real domicile" both land. Swap the matcher for a
 * search API without changing the surrounding UI. */

function score(haystack: string, terms: string[]) {
  const hay = haystack.toLowerCase();
  return terms.every((t) => hay.includes(t)) ? terms.join("").length : 0;
}

export function SearchOverlay({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const results = useMemo(() => {
    const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    if (!terms.length) return [];
    return products
      .map((p) => ({ p, s: score(`${p.name} ${p.team} ${p.season} ${p.league}`, terms) }))
      .filter((r) => r.s > 0)
      .slice(0, 8)
      .map((r) => r.p);
  }, [query]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={transition.fast}
      className="fixed inset-0 z-[80] bg-void/92 backdrop-blur-2xl"
      role="dialog"
      aria-modal="true"
      aria-label="Recherche"
    >
      <div className="mx-auto max-w-3xl px-5 pt-24">
        <div className="flex items-center gap-4 border-b border-ink/15 pb-4">
          <Search size={24} className="shrink-0 text-steel-500" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Club, sélection, saison…"
            aria-label="Rechercher un produit"
            className="w-full bg-transparent font-display text-2xl uppercase tracking-tight text-ink outline-none placeholder:text-steel-600 md:text-4xl"
          />
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer la recherche"
            className="shrink-0 text-steel-400 hover:text-ink"
          >
            <X size={24} />
          </button>
        </div>

        <div className="mt-6 max-h-[60vh] overflow-y-auto">
          {query && results.length === 0 && (
            <p className="py-10 text-center text-steel-400">
              Aucun résultat pour «&nbsp;{query}&nbsp;».
            </p>
          )}

          {!query && (
            <div className="flex flex-wrap gap-2 pt-2">
              <span className="label-mono w-full pb-2 text-steel-500">Recherches fréquentes</span>
              {["Real Madrid", "PSG", "Brésil", "Rétro", "Édition spéciale"].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setQuery(s)}
                  className="rounded-full border border-ink/12 px-4 py-2 text-sm text-steel-300 transition-colors hover:border-pitch/50 hover:text-pitch"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <ul>
            {results.map((p, i) => (
              <motion.li
                key={p.slug}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...transition.fast, delay: i * 0.03 }}
              >
                <Link
                  href={`/produit/${p.slug}`}
                  onClick={onClose}
                  className="flex items-center gap-4 rounded-md px-3 py-3 transition-colors hover:bg-ink/5"
                >
                  <div className="h-14 w-14 shrink-0">
                    <Jersey colorway={p.colorway} detailed={false} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-ink">{p.name}</p>
                    <p className="label-mono text-steel-500">{p.league}</p>
                  </div>
                  <span className="tabular shrink-0 text-sm text-steel-300">
                    {formatPrice(p.price)}
                  </span>
                </Link>
              </motion.li>
            ))}
          </ul>
        </div>
      </div>
    </motion.div>
  );
}
