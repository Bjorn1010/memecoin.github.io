"use client";

import { useState } from "react";
import { AnimatePresence } from "motion/react";
import type { Product } from "@/lib/types";
import { ProductCard } from "@/components/products/ProductCard";
import { QuickView } from "@/components/products/QuickView";

export function ProductGrid({
  products,
  columns = 4,
}: {
  products: Product[];
  columns?: 3 | 4;
}) {
  const [quickView, setQuickView] = useState<Product | null>(null);

  const cols =
    columns === 3
      ? "grid-cols-2 md:grid-cols-3"
      : "grid-cols-2 md:grid-cols-3 xl:grid-cols-4";

  return (
    <>
      <div className={`grid gap-x-4 gap-y-10 md:gap-x-6 ${cols}`}>
        {products.map((p, i) => (
          <ProductCard key={p.slug} product={p} index={i} onQuickView={setQuickView} />
        ))}
      </div>

      <AnimatePresence>
        {quickView && <QuickView product={quickView} onClose={() => setQuickView(null)} />}
      </AnimatePresence>
    </>
  );
}

/** Matches the card's aspect ratio so swapping in real data causes no shift. */
export function ProductGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-3 md:gap-x-6 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i}>
          <div className="skeleton aspect-4/5 rounded-lg" />
          <div className="mt-4 space-y-2">
            <div className="skeleton h-2.5 w-1/3 rounded-xs" />
            <div className="skeleton h-3.5 w-4/5 rounded-xs" />
            <div className="skeleton h-3.5 w-1/4 rounded-xs" />
          </div>
        </div>
      ))}
    </div>
  );
}
