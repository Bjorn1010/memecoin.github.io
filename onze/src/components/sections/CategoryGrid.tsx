"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import { Img } from "@/components/ui/Img";
import { cn } from "@/lib/utils";

/* Shop by category.
 *
 * Six entrances, not six cards: the first tile spans two columns so the row
 * has a clear point of entry instead of six identical rectangles competing.
 * Each tile carries an image, a name, one line of why, and a visible action —
 * the brief's requirement, and also what stops a category grid reading as
 * decoration a shopper scrolls past. */

export type Category = {
  href: string;
  title: string;
  blurb: string;
  image: string;
  count?: number;
  wide?: boolean;
};

export function CategoryGrid({ categories }: { categories: Category[] }) {
  const reduced = useReducedMotion();

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {categories.map((cat, i) => (
        <motion.div
          key={cat.href}
          initial={reduced ? undefined : { opacity: 0, y: 30 }}
          whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.7, delay: Math.min(i, 5) * 0.06, ease: [0.16, 1, 0.3, 1] }}
          className={cn(cat.wide && "col-span-2")}
        >
          <Link
            href={cat.href}
            data-cursor="Explorer"
            /* `isolate` is load-bearing: the photograph below is -z-10, and
               without a stacking context here it paints behind this element's
               own bg-base and the card renders as a black box. */
            className="group relative isolate flex h-full min-h-[300px] flex-col justify-end overflow-hidden border border-line bg-base p-5 transition-colors hover:border-steel-600 lg:min-h-[420px] lg:p-7"
          >
            <div className="absolute inset-0 -z-10 overflow-hidden">
              <Img
                name={cat.image}
                alt=""
                ratio={cat.wide ? "16/9" : "4/5"}
                sizes="(max-width: 640px) 50vw, (max-width: 1024px) 50vw, 25vw"
                className={cn(
                  "h-full w-full object-cover transition-transform duration-[--duration-cinematic] ease-[--ease-out-expo]",
                  !reduced && "group-hover:scale-[1.06]",
                )}
              />
            </div>
            {/* Weighted to the bottom where the label sits: a bright photo needs
                far more veil under the text than a dark one. */}
            <div
              aria-hidden
              className="absolute inset-0 -z-10 bg-gradient-to-t from-void via-void/55 to-void/5 transition-opacity duration-[--duration-slow] group-hover:from-void group-hover:via-void/70"
            />

            <div className="relative">
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-display text-xl leading-none text-ink lg:text-2xl">
                  {cat.title}
                </h3>
                <ArrowUpRight
                  size={18}
                  className="mt-0.5 shrink-0 text-steel-300 transition-all duration-[--duration-standard] group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-volt"
                />
              </div>
              <p className="mt-2 max-w-xs text-xs leading-relaxed text-steel-300 lg:text-sm">
                {cat.blurb}
              </p>
              {cat.count !== undefined && (
                <p className="label-mono mt-3 text-steel-500">{cat.count} références</p>
              )}
            </div>
          </Link>
        </motion.div>
      ))}
    </div>
  );
}
