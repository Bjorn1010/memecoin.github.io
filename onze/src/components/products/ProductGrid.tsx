import type { Product } from "@/lib/types";
import { ProductCard } from "@/components/products/ProductCard";

export function ProductGrid({
  products,
  columns = 4,
  /** How many cards sit above the fold and should not lazy-load their kit. */
  priorityCount = 0,
}: {
  products: Product[];
  columns?: 3 | 4;
  priorityCount?: number;
}) {
  const cols =
    columns === 3 ? "grid-cols-2 md:grid-cols-3" : "grid-cols-2 md:grid-cols-3 xl:grid-cols-4";

  return (
    <div className={`grid gap-x-4 gap-y-10 md:gap-x-6 ${cols}`}>
      {products.map((p, i) => (
        <ProductCard key={p.slug} product={p} index={i} priority={i < priorityCount} />
      ))}
    </div>
  );
}

/** Matches the card's aspect ratio so swapping in real data causes no shift. */
export function ProductGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-3 md:gap-x-6 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i}>
          <div className="skeleton aspect-4/5" />
          <div className="mt-4 space-y-2">
            <div className="skeleton h-2.5 w-1/3" />
            <div className="skeleton h-3.5 w-4/5" />
            <div className="skeleton h-3.5 w-1/4" />
          </div>
        </div>
      ))}
    </div>
  );
}
