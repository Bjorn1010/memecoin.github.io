"use client";

import Link from "next/link";
import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Check, Heart, Plus } from "lucide-react";
import type { Product } from "@/lib/types";
import { KitVisual } from "@/components/ui/KitVisual";
import { Price } from "@/components/ui/Price";
import { useCart } from "@/components/cart/CartProvider";
import { transition } from "@/lib/motion";
import { cn, discountPercent } from "@/lib/utils";

/* The product card.
 *
 * Two things carry it. First, a real second view: hovering cross-fades the
 * front of the shirt to its back, which is the view with the number on it —
 * the thing a shirt buyer actually wants to see, and a better use of the
 * interaction than a zoom.
 *
 * Second, quick add. The old card added a sizeless product straight to the
 * cart, which is not an order anyone can fulfil. Now the button reveals the
 * sizes in place, and only a chosen size adds the line. Everything here is
 * reachable by tap: nothing is hover-only.
 */

export function ProductCard({
  product,
  index = 0,
  priority = false,
}: {
  product: Product;
  index?: number;
  priority?: boolean;
}) {
  const reduced = useReducedMotion();
  const { add, open } = useCart();
  const [hovered, setHovered] = useState(false);
  const [picking, setPicking] = useState(false);
  const [added, setAdded] = useState(false);
  const [wishlisted, setWishlisted] = useState(false);

  const soldOut = product.stock === 0;
  const off = discountPercent(product.price, product.compareAt);
  /* One badge, in order of what a shopper most needs to know. Stacking four
     labels on a photo is how a premium card turns into a discount sticker. */
  const badge = soldOut
    ? { text: "Épuisé", tone: "muted" as const }
    : off
      ? { text: `−${off}%`, tone: "sale" as const }
      : product.isNew
        ? { text: "Nouveau", tone: "volt" as const }
        : product.category === "editions-speciales"
          ? { text: "Limitée", tone: "cup" as const }
          : null;

  function choose(size: string) {
    add(product, size, 1);
    setPicking(false);
    setAdded(true);
    open();
    window.setTimeout(() => setAdded(false), 1600);
  }

  return (
    <motion.article
      initial={reduced ? undefined : { opacity: 0, y: 24 }}
      whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ ...transition.premium, delay: Math.min(index, 7) * 0.04 }}
      className="group relative flex flex-col"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => {
        setHovered(false);
        setPicking(false);
      }}
    >
      <div className="relative aspect-4/5 overflow-hidden border border-line bg-base transition-colors duration-[--duration-standard] group-hover:border-steel-600">
        <Link
          href={`/produit/${product.slug}`}
          className="absolute inset-0 z-10"
          aria-label={`${product.name}, ${soldOut ? "épuisé" : "voir le produit"}`}
        />

        {/* Club colour wash, lifted on hover — the card's only ambient colour. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-30 transition-opacity duration-[--duration-slow] group-hover:opacity-60"
          style={{
            background: `radial-gradient(70% 60% at 50% 108%, ${product.colorway.primary}66, transparent 72%)`,
          }}
        />

        {/* Front and back stacked; hover cross-fades between them. */}
        <div
          className={cn(
            "absolute inset-0 p-7 transition-transform duration-[--duration-premium] ease-[--ease-out-expo]",
            !reduced && "group-hover:scale-[1.04]",
            soldOut && "opacity-40 saturate-0",
          )}
        >
          <div
            className={cn(
              "h-full transition-opacity duration-[--duration-slow]",
              hovered && !reduced ? "opacity-0" : "opacity-100",
            )}
          >
            <KitVisual
              colorway={product.colorway}
              photo={product.photo}
              alt={product.name}
              monogram={product.teamSlug.slice(0, 3).toUpperCase()}
              number="10"
              priority={priority}
            />
          </div>
          <div
            aria-hidden
            className={cn(
              "absolute inset-0 p-7 transition-opacity duration-[--duration-slow]",
              hovered && !reduced ? "opacity-100" : "opacity-0",
            )}
          >
            <KitVisual
              colorway={product.colorway}
              photo={product.photo}
              alt=""
              view="back"
              number="10"
              playerName={product.team.toUpperCase()}
            />
          </div>
        </div>

        {badge && (
          <span
            className={cn(
              "label-mono absolute left-3 top-3 z-20 px-2 py-1",
              badge.tone === "sale" && "bg-sale text-void",
              badge.tone === "volt" && "bg-volt text-on-volt",
              badge.tone === "cup" && "bg-cup text-void",
              badge.tone === "muted" && "bg-steel-700 text-steel-200",
            )}
          >
            {badge.text}
          </span>
        )}

        <button
          type="button"
          onClick={() => setWishlisted((w) => !w)}
          aria-pressed={wishlisted}
          aria-label={wishlisted ? `Retirer ${product.name} de la wishlist` : `Ajouter ${product.name} à la wishlist`}
          className={cn(
            "absolute right-3 top-3 z-20 grid h-9 w-9 place-items-center border transition-colors",
            wishlisted
              ? "border-sale/50 bg-sale/15 text-sale"
              : "border-line bg-void/70 text-steel-300 backdrop-blur-sm hover:text-ink",
          )}
        >
          <Heart size={15} fill={wishlisted ? "currentColor" : "none"} strokeWidth={1.75} />
        </button>

        {/* Quick add. Always present on touch, revealed on hover on a pointer
            device — never the only route to the product, which is the link. */}
        {!soldOut && (
          <div className="absolute inset-x-3 bottom-3 z-20">
            <AnimatePresence mode="wait" initial={false}>
              {added ? (
                <motion.p
                  key="added"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center justify-center gap-2 bg-volt py-3 font-display text-xs uppercase tracking-wide text-on-volt"
                >
                  <Check size={14} strokeWidth={3} /> Ajouté
                </motion.p>
              ) : picking ? (
                <motion.div
                  key="sizes"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex flex-wrap gap-1 bg-void/90 p-1.5 backdrop-blur-md"
                >
                  {product.sizes.map((size) => (
                    <button
                      key={size}
                      type="button"
                      onClick={() => choose(size)}
                      className="number-plate min-w-9 flex-1 bg-surface py-2 text-xs text-ink transition-colors hover:bg-volt hover:text-on-volt"
                    >
                      {size}
                    </button>
                  ))}
                </motion.div>
              ) : (
                /* Deliberately not a motion component. Motion writes the
                   animated opacity to the inline style, which outranks the
                   `lg:opacity-0` class and left this button permanently
                   visible on desktop instead of revealing on hover. CSS owns
                   the reveal; on touch there is no hover, so it is always on. */
                <button
                  key="cta"
                  type="button"
                  onClick={() => setPicking(true)}
                  className={cn(
                    "flex w-full items-center justify-center gap-2 bg-ink py-3 font-display text-xs uppercase tracking-wide text-void transition-colors hover:bg-volt hover:text-on-volt",
                    "lg:translate-y-1.5 lg:opacity-0 lg:transition-all lg:duration-[--duration-standard] lg:group-hover:translate-y-0 lg:group-hover:opacity-100 lg:focus-visible:translate-y-0 lg:focus-visible:opacity-100",
                  )}
                >
                  <Plus size={14} strokeWidth={3} /> Choisir la taille
                </button>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      <div className="mt-4 space-y-1.5">
        <p className="label-mono text-steel-500">
          {product.team} · {product.season}
        </p>
        <h3 className="text-sm leading-snug text-ink">
          <Link href={`/produit/${product.slug}`} className="transition-colors hover:text-volt">
            {product.name}
          </Link>
        </h3>
        {/* Wraps rather than overlapping: on a two-column phone grid the card
            is ~170px wide, and a discounted price plus a stock label do not
            fit on one line. */}
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <Price price={product.price} compareAt={product.compareAt} size="sm" />
          <p
            className={cn(
              "label-mono",
              soldOut ? "text-steel-500" : product.stock <= 3 ? "text-sale" : "text-steel-500",
            )}
          >
            {soldOut ? "Épuisé" : product.stock <= 3 ? `Plus que ${product.stock}` : "En stock"}
          </p>
        </div>
      </div>
    </motion.article>
  );
}
