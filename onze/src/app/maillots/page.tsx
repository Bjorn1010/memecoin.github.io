import type { Metadata } from "next";
import { Suspense } from "react";
import { CatalogueView } from "@/components/catalogue/CatalogueView";
import { products } from "@/lib/data/products";

export const metadata: Metadata = {
  title: "Tous les maillots",
  description:
    "Maillots de football domicile, extérieur et third. Premier League, Liga, Serie A, Bundesliga, Ligue 1 et sélections nationales. Flocage inclus.",
  alternates: { canonical: "/maillots" },
};

/* Query parameters are read client-side rather than on the server, which keeps
 * this route statically exportable — the whole site can then ship as flat HTML
 * to any static host. useSearchParams needs a Suspense boundary to do that. */
export default function MaillotsPage() {
  return (
    <Suspense fallback={<div className="min-h-[60svh]" />}>
      <CatalogueView products={products} eyebrow="Catalogue complet" title="Tous les maillots" />
    </Suspense>
  );
}
