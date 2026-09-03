"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Check, X } from "lucide-react";
import type { Product } from "@/lib/types";
import { Jersey } from "@/components/ui/Jersey";
import { Price } from "@/components/ui/Price";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useCart } from "@/components/cart/CartProvider";
import { scrim, spring, transition } from "@/lib/motion";
import { cn } from "@/lib/utils";

/* Buy without leaving the grid. Deliberately shows less than the full product
 * page — size, price, one CTA — so it stays a shortcut rather than a second
 * product page to maintain. */

export function QuickView({ product, onClose }: { product: Product; onClose: () => void }) {
  const [size, setSize] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const { add } = useCart();

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  function handleAdd() {
    if (!size) {
      setError(true);
      return;
    }
    add(product, size);
    onClose();
  }

  return (
    <>
      <motion.div
        variants={scrim}
        initial="hidden"
        animate="visible"
        exit="exit"
        onClick={onClose}
        className="fixed inset-0 z-[95] bg-ink/75 backdrop-blur-md"
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 20 }}
        transition={spring.panel}
        role="dialog"
        aria-modal="true"
        aria-label={`Aperçu rapide : ${product.name}`}
        className="fixed left-1/2 top-1/2 z-[96] w-[min(920px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-xl border border-ink/12 bg-base shadow-[0_4px_8px_rgb(0_0_0/0.5),0_20px_56px_rgb(0_0_0/0.45)]"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer l'aperçu"
          className="absolute right-4 top-4 z-10 grid h-9 w-9 place-items-center rounded-full bg-ink/50 text-steel-300 backdrop-blur-sm hover:text-ink"
        >
          <X size={18} />
        </button>

        <div className="grid md:grid-cols-2">
          <div className="relative aspect-square bg-gradient-to-b from-white to-pitch-tint p-8">
            <div
              aria-hidden
              className="absolute inset-0"
              style={{
                background: `radial-gradient(60% 50% at 50% 100%, ${product.colorway.primary}44, transparent 70%)`,
              }}
            />
            <div className="relative h-full">
              <Jersey
                colorway={product.colorway}
                monogram={product.teamSlug.slice(0, 3).toUpperCase()}
                number="10"
              />
            </div>
          </div>

          <div className="flex flex-col p-7">
            <div className="mb-3 flex gap-2">
              {product.compareAt && <Badge tone="sale">Promo</Badge>}
              {product.isNew && <Badge tone="new">Nouveau</Badge>}
            </div>

            <p className="label-mono text-steel-500">
              {product.team} · {product.season}
            </p>
            <h2 className="mt-2 font-display text-2xl uppercase leading-tight text-ink">
              {product.name}
            </h2>
            <Price price={product.price} compareAt={product.compareAt} size="lg" className="mt-4" />

            <fieldset className="mt-7">
              <legend className="label-mono mb-3 text-steel-400">
                Taille
                {error && <span className="ml-2 text-sale">— sélectionnez une taille</span>}
              </legend>
              <div className="flex flex-wrap gap-2">
                {product.sizes.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => {
                      setSize(s);
                      setError(false);
                    }}
                    aria-pressed={size === s}
                    className={cn(
                      "h-11 min-w-[3rem] rounded-sm border px-3 text-sm transition-colors",
                      size === s
                        ? "border-pitch bg-pitch text-paper"
                        : "border-ink/15 text-steel-200 hover:border-ink/40",
                      error && !size && "border-sale/50",
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </fieldset>

            <p className="mt-5 flex items-center gap-2 text-xs text-steel-400">
              <Check size={14} className="text-success" />
              {product.stock > 0 ? `En stock — ${product.stock} pièces` : "Épuisé"}
            </p>

            <div className="mt-auto space-y-3 pt-7">
              <Button size="lg" className="w-full" onClick={handleAdd} disabled={product.stock === 0}>
                Ajouter au panier
              </Button>
              <Link
                href={`/produit/${product.slug}`}
                onClick={onClose}
                className="label-mono block text-center text-steel-400 transition-colors hover:text-ink"
              >
                Voir la fiche complète
              </Link>
            </div>
          </div>
        </div>
      </motion.div>
    </>
  );
}
