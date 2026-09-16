import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { CatalogueView } from "@/components/catalogue/CatalogueView";
import { TeamHero } from "@/components/sections/TeamHero";
import { clubs, teamBySlug } from "@/lib/data/teams";
import { products } from "@/lib/data/products";

export function generateStaticParams() {
  return clubs.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata(props: PageProps<"/clubs/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const team = teamBySlug(slug);
  if (!team) return {};
  const count = products.filter((p) => p.teamSlug === slug).length;
  const description = `Maillots ${team.name} : domicile, extérieur, third et rétros. ${count} références, flocage nom et numéro inclus, expédition 48 h.`;
  return {
    title: `Maillots ${team.name}`,
    description,
    alternates: { canonical: `/clubs/${slug}` },
    openGraph: { title: `Maillots ${team.name} — ONZE`, description },
  };
}

export default async function ClubPage(props: PageProps<"/clubs/[slug]">) {
  const { slug } = await props.params;
  const team = teamBySlug(slug);
  if (!team || team.league === "Sélections") notFound();

  const scoped = products.filter((p) => p.teamSlug === slug);

  return (
    <>
      <TeamHero team={team} count={scoped.length} kicker={team.league} />
      {/* The club is already fixed by the route, so its facet is locked out of
          the filter panel rather than shown with every other option greyed. */}
      <Suspense fallback={<div className="min-h-[60svh]" />}>
        <CatalogueView
          products={scoped}
          eyebrow={team.league}
          title={`Maillots ${team.name}`}
          description={`Tous les maillots ${team.name} disponibles, saison en cours et archives.`}
          lockedFacets={["club", "pays", "league"]}
        />
      </Suspense>
    </>
  );
}
