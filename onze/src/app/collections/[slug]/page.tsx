import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { CatalogueView } from "@/components/catalogue/CatalogueView";
import { collections, collectionBySlug } from "@/lib/data/collections";
import { products } from "@/lib/data/products";
import type { Filters } from "@/lib/catalogue";

export function generateStaticParams() {
  return collections.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata(
  props: PageProps<"/collections/[slug]">,
): Promise<Metadata> {
  const { slug } = await props.params;
  const collection = collectionBySlug(slug);
  if (!collection) return {};
  return {
    title: collection.title,
    description: collection.tagline,
    alternates: { canonical: `/collections/${slug}` },
    openGraph: { title: `${collection.title} — ONZE`, description: collection.tagline },
  };
}

export default async function CollectionPage(props: PageProps<"/collections/[slug]">) {
  const { slug } = await props.params;
  const collection = collectionBySlug(slug);
  if (!collection) notFound();

  /* "Nouveautés" is a cross-category cut rather than a category, so it filters
     the product list directly instead of locking a facet. */
  const isNew = collection.category === "nouveautes";
  const scoped = isNew ? products.filter((p) => p.isNew) : products;

  /* Narrowed on the field itself rather than via `isNew`, so TypeScript can see
     that "nouveautes" is excluded from the Category union in the else branch. */
  const initialFilters: Partial<Filters> =
    collection.category === "nouveautes" ? {} : { category: [collection.category] };

  /* CatalogueView reads query parameters client-side, which requires a Suspense
     boundary for the static export to prerender this page. */
  return (
    <Suspense fallback={<div className="min-h-[60svh]" />}>
      <CatalogueView
        products={scoped}
        eyebrow="Collection"
        title={collection.title}
        initialFilters={initialFilters}
        lockedFacets={isNew ? [] : ["category"]}
      />
    </Suspense>
  );
}
