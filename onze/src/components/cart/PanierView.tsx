"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { Minus, Plus, ShoppingBag, Trash2, Truck } from "lucide-react";
import { useCart } from "@/components/cart/CartProvider";
import { Jersey } from "@/components/ui/Jersey";
import { Button } from "@/components/ui/Button";
import { formatPrice } from "@/lib/utils";
import { spring, transition } from "@/lib/motion";

/* The full cart page. The drawer is for a quick glance after adding; this is
 * where quantities actually get reviewed before paying, so it shows the line
 * maths the drawer hides. */

const FREE_SHIPPING = 120;

export function PanierView() {
  const { lines, subtotal, count, setQuantity, remove, clear } = useCart();

  if (count === 0) {
    return (
      <div className="mx-auto flex min-h-[70svh] max-w-lg flex-col items-center justify-center px-5 text-center">
        <div className="grid h-20 w-20 place-items-center rounded-full bg-pitch-tint">
          <ShoppingBag size={32} strokeWidth={1.5} className="text-volt" />
        </div>
        <h1 className="mt-7 font-display text-title text-ink">Panier vide</h1>
        <p className="mt-3 text-sm leading-relaxed text-steel-400">
          Les nouveautés 26/27 viennent d&apos;arriver. Flocage inclus sur tout le
          catalogue.
        </p>
        <Button href="/maillots" size="lg" className="mt-8">
          Explorer les maillots
        </Button>
      </div>
    );
  }

  const remaining = Math.max(0, FREE_SHIPPING - subtotal);
  const progress = Math.min(100, (subtotal / FREE_SHIPPING) * 100);

  return (
    <div className="mx-auto max-w-[1200px] px-5 pt-32 pb-24 lg:px-10">
      <header className="mb-10 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-mono mb-3 flex items-center gap-3 text-volt">
            <span className="inline-block h-px w-8 bg-pitch" />
            Votre sélection
          </p>
          <h1 className="font-display text-display text-ink">Panier</h1>
        </div>
        <p className="scoreboard text-2xl text-steel-400">
          {count}
          <span className="ml-2 font-sans text-xs font-normal uppercase tracking-[0.14em] text-steel-500">
            article{count > 1 ? "s" : ""}
          </span>
        </p>
      </header>

      <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr]">
        {/* Lines */}
        <div>
          <ul className="border-t border-ink/10">
            <AnimatePresence initial={false}>
              {lines.map((line) => (
                <motion.li
                  key={`${line.productId}-${line.size}`}
                  layout
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                  transition={spring.panel}
                  className="flex gap-5 overflow-hidden border-b border-ink/10 py-6"
                >
                  <Link
                    href={`/produit/${line.slug}`}
                    className="h-28 w-24 shrink-0 rounded-md bg-pitch-tint p-2"
                  >
                    <Jersey colorway={line.colorway} detailed={false} />
                  </Link>

                  <div className="flex min-w-0 flex-1 flex-col">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="label-mono text-steel-500">{line.team}</p>
                        <h2 className="mt-1 truncate text-sm font-medium text-ink">
                          <Link href={`/produit/${line.slug}`} className="hover:text-volt">
                            {line.name}
                          </Link>
                        </h2>
                        <p className="label-mono mt-1.5 text-steel-500">Taille {line.size}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => remove(line.productId, line.size)}
                        aria-label={`Retirer ${line.name} du panier`}
                        className="shrink-0 rounded-sm p-1.5 text-steel-500 transition-colors hover:text-sale"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>

                    <div className="mt-auto flex items-end justify-between pt-4">
                      <div className="flex items-center rounded-md border border-ink/15">
                        <button
                          type="button"
                          onClick={() => setQuantity(line.productId, line.size, line.quantity - 1)}
                          aria-label={`Réduire la quantité de ${line.name}`}
                          className="grid h-10 w-10 place-items-center text-steel-400 transition-colors hover:text-ink"
                        >
                          <Minus size={14} />
                        </button>
                        <span className="tabular w-8 text-center text-sm text-ink">
                          {line.quantity}
                        </span>
                        <button
                          type="button"
                          onClick={() => setQuantity(line.productId, line.size, line.quantity + 1)}
                          aria-label={`Augmenter la quantité de ${line.name}`}
                          className="grid h-10 w-10 place-items-center text-steel-400 transition-colors hover:text-ink"
                        >
                          <Plus size={14} />
                        </button>
                      </div>

                      <div className="text-right">
                        {/* The per-unit price only earns its place once there is
                            more than one, otherwise it just repeats the total. */}
                        {line.quantity > 1 && (
                          <p className="tabular text-xs text-steel-500">
                            {formatPrice(line.price)} × {line.quantity}
                          </p>
                        )}
                        <p className="tabular mt-0.5 font-semibold text-ink">
                          {formatPrice(line.price * line.quantity)}
                        </p>
                      </div>
                    </div>
                  </div>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
            <Link
              href="/maillots"
              className="label-mono text-steel-500 transition-colors hover:text-volt"
            >
              ← Continuer mes achats
            </Link>
            <button
              type="button"
              onClick={clear}
              className="label-mono text-steel-500 transition-colors hover:text-sale"
            >
              Vider le panier
            </button>
          </div>
        </div>

        {/* Summary */}
        <aside className="lg:sticky lg:top-28 lg:self-start">
          <div className="rounded-xl border border-ink/10 bg-surface p-6 shadow-[0_2px_4px_rgb(5_52_28_/_0.07),0_10px_28px_rgb(5_52_28_/_0.09)]">
            <h2 className="label-mono mb-5 text-ink">Récapitulatif</h2>

            <div className="mb-6">
              <p className="mb-2 text-xs text-steel-500">
                {remaining > 0 ? (
                  <>
                    Plus que{" "}
                    <span className="tabular font-semibold text-volt">
                      {formatPrice(remaining)}
                    </span>{" "}
                    pour la livraison offerte
                  </>
                ) : (
                  <span className="font-semibold text-volt">Livraison offerte débloquée</span>
                )}
              </p>
              <div className="h-1.5 overflow-hidden rounded-full bg-steel-800">
                <motion.div
                  className="h-full rounded-full bg-pitch"
                  initial={false}
                  animate={{ width: `${progress}%` }}
                  transition={transition.slow}
                />
              </div>
            </div>

            <dl className="space-y-3 border-t border-ink/10 pt-5 text-sm">
              <div className="flex justify-between">
                <dt className="text-steel-400">Sous-total</dt>
                <dd className="tabular text-ink">{formatPrice(subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-steel-400">Livraison</dt>
                <dd className="tabular text-ink">
                  {remaining > 0 ? "Calculée au paiement" : "Offerte"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-steel-400">Flocage</dt>
                <dd className="font-semibold text-volt">Inclus</dd>
              </div>
            </dl>

            <div className="mt-5 flex items-baseline justify-between border-t border-ink/10 pt-5">
              <span className="label-mono text-steel-500">Total</span>
              <motion.span
                key={subtotal}
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={transition.fast}
                className="scoreboard text-3xl text-ink"
              >
                {formatPrice(subtotal)}
              </motion.span>
            </div>

            <Button href="/checkout" size="lg" className="mt-6 w-full">
              Passer commande
            </Button>

            <p className="mt-4 flex items-start gap-2 text-xs leading-relaxed text-steel-500">
              <Truck size={14} className="mt-0.5 shrink-0 text-volt" />
              Expédition sous 48 h ouvrables depuis la Suisse, suivi inclus.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
