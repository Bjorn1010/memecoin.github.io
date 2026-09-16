"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "lucide-react";
import type { Product } from "@/lib/types";
import { KitVisual } from "@/components/ui/KitVisual";
import { ProductCard } from "@/components/products/ProductCard";
import { Price } from "@/components/ui/Price";

/* Just dropped.
 *
 * One shirt at campaign scale, three beside it — the asymmetry is the point.
 * A four-up grid says "here are four products"; this says "here is the one,
 * and here is what else landed with it", which is how a drop is actually
 * announced. The feature panel is its own layout rather than a stretched
 * card, because a card scaled to twice the size just looks like a bug. */
export function JustDropped({ products }: { products: Product[] }) {
  const reduced = useReducedMotion();
  const [feature, ...rest] = products;
  if (!feature) return null;

  return (
    <div className="grid gap-4 lg:grid-cols-[1.15fr_1fr]">
      <motion.article
        initial={reduced ? undefined : { opacity: 0, y: 30 }}
        whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        className="group relative flex min-h-[520px] flex-col justify-between overflow-hidden border border-line bg-base p-7 lg:min-h-[640px] lg:p-10"
      >
        <Link
          href={`/produit/${feature.slug}`}
          className="absolute inset-0 z-20"
          aria-label={`${feature.name}, voir le produit`}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-45 transition-opacity duration-[--duration-premium] group-hover:opacity-75"
          style={{
            background: `radial-gradient(65% 55% at 50% 105%, ${feature.colorway.primary}88, transparent 72%),
                         radial-gradient(40% 40% at 12% 8%, ${feature.colorway.secondary}44, transparent 70%)`,
          }}
        />
        <span
          aria-hidden
          className="pointer-events-none absolute -right-8 top-4 font-display text-[11rem] leading-none text-ink/5 lg:text-[15rem]"
        >
          {feature.season.replace("/", "")}
        </span>

        <div className="relative z-10 flex items-start justify-between gap-4">
          <div>
            <p className="eyebrow label-mono mb-4">Le drop</p>
            <h3 className="font-display text-title text-ink">{feature.name}</h3>
            <p className="label-mono mt-2 text-steel-400">
              {feature.team} · {feature.league}
            </p>
          </div>
        </div>

        <div className="pointer-events-none relative z-0 mx-auto my-6 w-full max-w-[300px] transition-transform duration-[--duration-premium] ease-[--ease-out-expo] group-hover:-translate-y-2 group-hover:scale-[1.04] lg:max-w-[360px]">
          <KitVisual
            colorway={feature.colorway}
            photo={feature.photo}
            alt={feature.name}
            monogram={feature.teamSlug.slice(0, 3).toUpperCase()}
            number="10"
          />
        </div>

        <div className="relative z-10 flex items-end justify-between gap-4 border-t border-line pt-5">
          <Price price={feature.price} compareAt={feature.compareAt} size="lg" />
          <span className="inline-flex items-center gap-2 font-display text-sm uppercase tracking-wide text-ink transition-colors group-hover:text-volt">
            Voir
            <ArrowRight size={16} strokeWidth={2.5} className="transition-transform group-hover:translate-x-1" />
          </span>
        </div>
      </motion.article>

      <div className="grid grid-cols-2 gap-x-4 gap-y-8 self-start lg:grid-cols-2">
        {rest.slice(0, 4).map((p, i) => (
          <ProductCard key={p.slug} product={p} index={i} />
        ))}
      </div>
    </div>
  );
}
