"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { motion, useMotionTemplate, useMotionValue, useSpring, useReducedMotion } from "motion/react";
import { Eye, Heart } from "lucide-react";
import type { Product } from "@/lib/types";
import { Jersey } from "@/components/ui/Jersey";
import { Badge } from "@/components/ui/Badge";
import { Price } from "@/components/ui/Price";
import { spring, transition } from "@/lib/motion";
import { cn } from "@/lib/utils";

/* The card carries most of the site's personality, so the hover is built from
 * four cheap effects layered rather than one big one:
 *   1. the kit tilts toward the pointer (transform only — no layout)
 *   2. a specular highlight tracks the pointer across the surface
 *   3. the kit lifts and scales very slightly
 *   4. metadata and the quick-view CTA fade up
 * All of it collapses to nothing under prefers-reduced-motion.
 */

export function ProductCard({
  product,
  index = 0,
  onQuickView,
}: {
  product: Product;
  index?: number;
  onQuickView?: (p: Product) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const [wishlisted, setWishlisted] = useState(false);

  /* Pointer position as a percentage of the card, driving the specular sweep. */
  const px = useMotionValue(50);
  const py = useMotionValue(50);
  /* Springs, or the tilt chases the cursor with visible lag. */
  const rx = useSpring(0, spring.pointer);
  const ry = useSpring(0, spring.pointer);
  const glare = useMotionTemplate`radial-gradient(circle at ${px}% ${py}%, rgba(255,255,255,0.14), transparent 55%)`;

  function handleMove(e: React.PointerEvent<HTMLDivElement>) {
    if (reduced || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const nx = (e.clientX - r.left) / r.width;
    const ny = (e.clientY - r.top) / r.height;
    px.set(nx * 100);
    py.set(ny * 100);
    /* Deliberately shallow: past ~8° a product card starts to look like a toy. */
    ry.set((nx - 0.5) * 12);
    rx.set(-(ny - 0.5) * 8);
  }

  function handleLeave() {
    px.set(50);
    py.set(50);
    rx.set(0);
    ry.set(0);
  }

  const soldOut = product.stock === 0;

  return (
    <motion.article
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ ...transition.premium, delay: Math.min(index, 7) * 0.05 }}
      className="group relative"
    >
      <div
        ref={ref}
        onPointerMove={handleMove}
        onPointerLeave={handleLeave}
        className="relative"
        style={{ perspective: 1000 }}
      >
        <Link
          href={`/produit/${product.slug}`}
          className="block focus-visible:outline-offset-4"
          aria-label={`${product.name}, ${product.stock === 0 ? "épuisé" : "voir le produit"}`}
        >
          <motion.div
            style={reduced ? undefined : { rotateX: rx, rotateY: ry, transformStyle: "preserve-3d" }}
            className={cn(
              "edge-lit relative aspect-4/5 overflow-hidden rounded-lg border border-white/8",
              "bg-gradient-to-b from-surface to-base transition-colors duration-[--duration-standard]",
              "group-hover:border-white/16",
            )}
          >
            {/* Club-tinted wash, revealed on hover. */}
            <div
              aria-hidden
              className="absolute inset-0 opacity-0 transition-opacity duration-[--duration-slow] group-hover:opacity-100"
              style={{
                background: `radial-gradient(65% 55% at 50% 105%, ${product.colorway.primary}44, transparent 70%)`,
              }}
            />

            {/* Pointer-tracked specular sweep. */}
            {!reduced && (
              <motion.div
                aria-hidden
                style={{ backgroundImage: glare }}
                className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-[--duration-standard] group-hover:opacity-100"
              />
            )}

            <div
              className={cn(
                "absolute inset-0 p-6 transition-transform duration-[--duration-premium] ease-[--ease-out-expo]",
                "group-hover:scale-[1.06]",
                soldOut && "opacity-45 saturate-0",
              )}
              style={{ transform: reduced ? undefined : "translateZ(40px)" }}
            >
              <Jersey
                colorway={product.colorway}
                monogram={product.teamSlug.slice(0, 3).toUpperCase()}
                number="10"
              />
            </div>

            {/* Badges */}
            <div className="absolute left-3 top-3 flex flex-col items-start gap-1.5">
              {product.compareAt && <Badge tone="sale">Promo</Badge>}
              {product.isNew && !product.compareAt && <Badge tone="new">Nouveau</Badge>}
              {product.category === "editions-speciales" && <Badge tone="limited">Limitée</Badge>}
              {soldOut && <Badge tone="soldout">Épuisé</Badge>}
            </div>

            {/* Quick view — appears on hover, and is always reachable by keyboard
                from the card link that follows it. */}
            {onQuickView && !soldOut && (
              <div className="absolute inset-x-3 bottom-3 translate-y-2 opacity-0 transition-all duration-[--duration-standard] ease-[--ease-out-expo] group-hover:translate-y-0 group-hover:opacity-100">
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    onQuickView(product);
                  }}
                  className="label-mono flex w-full items-center justify-center gap-2 rounded-sm bg-white/10 py-3 text-white backdrop-blur-md transition-colors hover:bg-volt hover:text-void"
                >
                  <Eye size={14} />
                  Aperçu rapide
                </button>
              </div>
            )}
          </motion.div>
        </Link>

        {/* Wishlist sits outside the link so it never triggers navigation. */}
        <button
          type="button"
          onClick={() => setWishlisted((w) => !w)}
          aria-pressed={wishlisted}
          aria-label={
            wishlisted ? `Retirer ${product.name} de la wishlist` : `Ajouter ${product.name} à la wishlist`
          }
          className={cn(
            "absolute right-3 top-3 grid h-9 w-9 place-items-center rounded-full border backdrop-blur-md transition-colors",
            wishlisted
              ? "border-sale/40 bg-sale/20 text-sale"
              : "border-white/12 bg-black/40 text-steel-300 hover:text-white",
          )}
        >
          <Heart size={15} fill={wishlisted ? "currentColor" : "none"} />
        </button>
      </div>

      {/* Metadata */}
      <div className="mt-4 space-y-1.5">
        <p className="label-mono text-steel-500">
          {product.team} · {product.season}
        </p>
        <h3 className="text-sm leading-snug text-white">
          <Link href={`/produit/${product.slug}`} className="hover:text-volt">
            {product.name}
          </Link>
        </h3>
        <Price price={product.price} compareAt={product.compareAt} size="sm" />
      </div>
    </motion.article>
  );
}
