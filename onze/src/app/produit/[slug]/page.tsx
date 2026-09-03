import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProductDetail } from "@/components/products/ProductDetail";
import { ProductGrid } from "@/components/products/ProductGrid";
import { SectionHeader } from "@/components/sections/SectionHeader";
import { getProduct, products, relatedTo } from "@/lib/data/products";

export function generateStaticParams() {
  return products.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata(
  props: PageProps<"/produit/[slug]">,
): Promise<Metadata> {
  const { slug } = await props.params;
  const product = getProduct(slug);
  if (!product) return {};

  const title = product.name;
  const description = `${product.description} ${product.compareAt ? "En promotion." : ""} Livraison 48 h.`.trim();

  return {
    title,
    description,
    alternates: { canonical: `/produit/${slug}` },
    openGraph: { title: `${title} — ONZE`, description, type: "website" },
  };
}

export default async function ProductPage(props: PageProps<"/produit/[slug]">) {
  const { slug } = await props.params;
  const product = getProduct(slug);
  if (!product) notFound();

  const related = relatedTo(product, 4);

  /* Product structured data. Rich results for a storefront are worth more than
     any amount of on-page keyword work. */
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.description,
    sku: product.id,
    brand: { "@type": "Brand", name: "ONZE" },
    category: product.category,
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: product.rating.toFixed(1),
      reviewCount: product.reviews,
    },
    offers: {
      "@type": "Offer",
      price: product.price.toFixed(2),
      priceCurrency: "CHF",
      availability:
        product.stock > 0
          ? "https://schema.org/InStock"
          : "https://schema.org/OutOfStock",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <ProductDetail product={product} />

      {related.length > 0 && (
        <section className="mx-auto max-w-[1600px] px-5 py-24 lg:px-10 lg:py-32">
          <SectionHeader
            eyebrow="Dans le même vestiaire"
            title="Vous aimerez aussi"
            href={`/maillots?club=${product.teamSlug}`}
            linkLabel={`Tout ${product.team}`}
          />
          <ProductGrid products={related} />
        </section>
      )}
    </>
  );
}
