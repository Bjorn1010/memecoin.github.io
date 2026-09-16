import type { Metadata } from "next";
import { Suspense } from "react";
import { CatalogueView } from "@/components/catalogue/CatalogueView";
import { products } from "@/lib/data/products";

export const metadata: Metadata = {
  title: "Promotions",
  description:
    "Maillots de football en promotion : fins de séries, saisons précédentes et tailles restantes. Flocage inclus, expédition 48 h.",
  alternates: { canonical: "/promotions" },
  openGraph: {
    title: "Promotions — ONZE",
    description: "Fins de séries et saisons précédentes, à prix réduit.",
  },
};

export default function PromotionsPage() {
  /* Derived from the catalogue itself — a product is on sale because it has a
     compareAt price, not because it was added to a manually curated list that
     can drift out of sync with the pricing. */
  const scoped = products.filter((p) => p.compareAt);

  return (
    <Suspense fallback={<div className="min-h-[60svh]" />}>
      <CatalogueView
        products={scoped}
        eyebrow="Last chance"
        title="Promotions"
        description="Fins de séries, saisons précédentes et dernières tailles. Les prix barrés sont les prix pratiqués avant réduction."
        lockedFacets={["promo"]}
      />
    </Suspense>
  );
}
