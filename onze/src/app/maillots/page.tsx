import type { Metadata } from "next";
import { CatalogueView } from "@/components/catalogue/CatalogueView";
import { products } from "@/lib/data/products";
import { teamBySlug } from "@/lib/data/teams";
import type { Filters } from "@/lib/catalogue";

export const metadata: Metadata = {
  title: "Tous les maillots",
  description:
    "Maillots de football domicile, extérieur et third. Premier League, Liga, Serie A, Bundesliga, Ligue 1 et sélections nationales. Flocage inclus.",
  alternates: { canonical: "/maillots" },
};

/* searchParams seeds the filters so links from the mega-menu ("?club=arsenal")
   land pre-narrowed. In Next 16 it is a Promise and must be awaited. */
export default async function MaillotsPage(props: PageProps<"/maillots">) {
  const sp = await props.searchParams;

  const one = (v: string | string[] | undefined) =>
    Array.isArray(v) ? v[0] : v;

  const club = one(sp.club);
  const pays = one(sp.pays);
  const taille = one(sp.taille);
  const saison = one(sp.saison);

  const initialFilters: Partial<Filters> = {
    club: club ? [club] : [],
    pays: pays ? [pays] : [],
    taille: taille ? [taille] : [],
    saison: saison ? [saison] : [],
  };

  const team = club ? teamBySlug(club) : pays ? teamBySlug(pays) : undefined;

  return (
    <CatalogueView
      products={products}
      eyebrow={team ? team.league : "Catalogue complet"}
      title={team ? team.name : "Tous les maillots"}
      initialFilters={initialFilters}
    />
  );
}
