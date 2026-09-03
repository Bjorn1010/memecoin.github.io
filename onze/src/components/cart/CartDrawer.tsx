"use client";

import Link from "next/link";
import { useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Minus, Plus, ShoppingBag, X } from "lucide-react";
import { useCart } from "@/components/cart/CartProvider";
import { Jersey } from "@/components/ui/Jersey";
import { Button } from "@/components/ui/Button";
import { formatPrice } from "@/lib/utils";
import { scrim, slideInRight, spring, transition } from "@/lib/motion";

const FREE_SHIPPING = 120;

export function CartDrawer() {
  const { isOpen, close, lines, subtotal, setQuantity, remove, lastAdded } = useCart();

  useEffect(() => {
    if (!isOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [isOpen, close]);

  const remaining = Math.max(0, FREE_SHIPPING - subtotal);
  const progress = Math.min(100, (subtotal / FREE_SHIPPING) * 100);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            variants={scrim}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={close}
            className="fixed inset-0 z-[85] bg-black/70 backdrop-blur-sm"
          />
          <motion.aside
            variants={slideInRight}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="fixed inset-y-0 right-0 z-[90] flex w-full max-w-md flex-col border-l border-white/10 bg-base"
            role="dialog"
            aria-modal="true"
            aria-label="Panier"
          >
            <header className="flex items-center justify-between border-b border-white/8 px-6 py-5">
              <h2 className="font-display text-xl uppercase text-white">Panier</h2>
              <button
                type="button"
                onClick={close}
                aria-label="Fermer le panier"
                className="grid h-9 w-9 place-items-center rounded-sm text-steel-400 hover:text-white"
              >
                <X size={20} />
              </button>
            </header>

            {lines.length === 0 ? (
              /* Empty state: never a bare "your cart is empty" — always a way out. */
              <div className="flex flex-1 flex-col items-center justify-center gap-5 px-8 text-center">
                <ShoppingBag size={40} strokeWidth={1.25} className="text-steel-600" />
                <div>
                  <p className="font-display text-lg uppercase text-white">Panier vide</p>
                  <p className="mt-2 text-sm text-steel-400">
                    Les nouveautés 26/27 viennent d&apos;arriver.
                  </p>
                </div>
                <Button href="/maillots" variant="outline" size="sm" onClick={close}>
                  Explorer les maillots
                </Button>
              </div>
            ) : (
              <>
                {/* Free-shipping meter — the one piece of persuasion in the drawer. */}
                <div className="border-b border-white/8 px-6 py-4">
                  <p className="mb-2 text-xs text-steel-400">
                    {remaining > 0 ? (
                      <>
                        Plus que <span className="tabular text-volt">{formatPrice(remaining)}</span>{" "}
                        pour la livraison offerte
                      </>
                    ) : (
                      <span className="text-volt">Livraison offerte débloquée</span>
                    )}
                  </p>
                  <div className="h-1 overflow-hidden rounded-full bg-steel-800">
                    <motion.div
                      className="h-full bg-volt"
                      initial={false}
                      animate={{ width: `${progress}%` }}
                      transition={transition.slow}
                    />
                  </div>
                </div>

                <ul className="flex-1 overflow-y-auto px-6 py-4">
                  <AnimatePresence initial={false}>
                    {lines.map((line) => {
                      const key = `${line.productId}-${line.size}`;
                      return (
                        <motion.li
                          key={key}
                          layout
                          initial={{ opacity: 0, x: 24 }}
                          animate={{
                            opacity: 1,
                            x: 0,
                            /* The just-added line gets a brief volt edge so the
                               eye lands on it without a toast. */
                            boxShadow:
                              lastAdded === key
                                ? ["0 0 0 0 #ccff0000", "0 0 0 2px #ccff0066", "0 0 0 0 #ccff0000"]
                                : undefined,
                          }}
                          exit={{ opacity: 0, x: 24, height: 0, marginBottom: 0 }}
                          transition={spring.panel}
                          className="mb-4 flex gap-4 rounded-md p-2"
                        >
                          <Link href={`/produit/${line.slug}`} onClick={close} className="h-24 w-20 shrink-0">
                            <Jersey colorway={line.colorway} detailed={false} />
                          </Link>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm text-white">{line.name}</p>
                            <p className="label-mono mt-1 text-steel-500">Taille {line.size}</p>
                            <div className="mt-3 flex items-center justify-between">
                              <div className="flex items-center gap-1 rounded-sm border border-white/12">
                                <button
                                  type="button"
                                  onClick={() => setQuantity(line.productId, line.size, line.quantity - 1)}
                                  aria-label={`Réduire la quantité de ${line.name}`}
                                  className="grid h-7 w-7 place-items-center text-steel-400 hover:text-white"
                                >
                                  <Minus size={13} />
                                </button>
                                <span className="tabular w-6 text-center text-xs text-white">
                                  {line.quantity}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => setQuantity(line.productId, line.size, line.quantity + 1)}
                                  aria-label={`Augmenter la quantité de ${line.name}`}
                                  className="grid h-7 w-7 place-items-center text-steel-400 hover:text-white"
                                >
                                  <Plus size={13} />
                                </button>
                              </div>
                              <span className="tabular text-sm text-white">
                                {formatPrice(line.price * line.quantity)}
                              </span>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => remove(line.productId, line.size)}
                            aria-label={`Retirer ${line.name} du panier`}
                            className="self-start text-steel-600 hover:text-sale"
                          >
                            <X size={16} />
                          </button>
                        </motion.li>
                      );
                    })}
                  </AnimatePresence>
                </ul>

                <footer className="border-t border-white/8 px-6 py-5">
                  <div className="mb-4 flex items-baseline justify-between">
                    <span className="label-mono text-steel-400">Sous-total</span>
                    <motion.span
                      key={subtotal}
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={transition.fast}
                      className="tabular font-display text-2xl text-white"
                    >
                      {formatPrice(subtotal)}
                    </motion.span>
                  </div>
                  <Button href="/checkout" size="lg" className="w-full" onClick={close}>
                    Passer commande
                  </Button>
                  <p className="mt-3 text-center text-xs text-steel-500">
                    Taxes et livraison calculées au paiement.
                  </p>
                </footer>
              </>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
