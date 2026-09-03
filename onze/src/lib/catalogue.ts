import type { Category, Product } from "@/lib/types";

/* Pure filter/sort layer. Kept free of React so the catalogue page, the
 * collection pages and any future search endpoint all narrow the same way. */

export interface Filters {
  club: string[];
  pays: string[];
  league: string[];
  kit: string[];
  saison: string[];
  taille: string[];
  category: Category[];
  promo: boolean;
  enStock: boolean;
  prixMax: number | null;
  q: string;
}

export const emptyFilters: Filters = {
  club: [],
  pays: [],
  league: [],
  kit: [],
  saison: [],
  taille: [],
  category: [],
  promo: false,
  enStock: false,
  prixMax: null,
  q: "",
};

export type SortKey = "pertinence" | "nouveautes" | "prix-asc" | "prix-desc" | "populaires";

export const SORT_LABELS: Record<SortKey, string> = {
  pertinence: "Pertinence",
  nouveautes: "Nouveautés",
  "prix-asc": "Prix croissant",
  "prix-desc": "Prix décroissant",
  populaires: "Les plus populaires",
};

/* Country entries live in the same team table as clubs, distinguished by
   league. The catalogue exposes them as separate facets because shoppers think
   "Brazil" and "Arsenal" as different kinds of thing. */
const isCountry = (p: Product) => p.league === "Sélections";

export function applyFilters(products: Product[], f: Filters): Product[] {
  const q = f.q.trim().toLowerCase();
  const terms = q ? q.split(/\s+/) : [];

  return products.filter((p) => {
    if (f.club.length && (isCountry(p) || !f.club.includes(p.teamSlug))) return false;
    if (f.pays.length && (!isCountry(p) || !f.pays.includes(p.teamSlug))) return false;
    if (f.league.length && !f.league.includes(p.league)) return false;
    if (f.kit.length && !f.kit.includes(p.kit)) return false;
    if (f.saison.length && !f.saison.includes(p.season)) return false;
    if (f.category.length && !f.category.includes(p.category)) return false;
    if (f.taille.length && !f.taille.some((s) => p.sizes.includes(s))) return false;
    if (f.promo && !p.compareAt) return false;
    if (f.enStock && p.stock === 0) return false;
    if (f.prixMax !== null && p.price > f.prixMax) return false;

    if (terms.length) {
      const hay = `${p.name} ${p.team} ${p.season} ${p.league} ${p.kit}`.toLowerCase();
      if (!terms.every((t) => hay.includes(t))) return false;
    }
    return true;
  });
}

export function sortProducts(products: Product[], key: SortKey): Product[] {
  const out = [...products];
  switch (key) {
    case "prix-asc":
      return out.sort((a, b) => a.price - b.price);
    case "prix-desc":
      return out.sort((a, b) => b.price - a.price);
    case "nouveautes":
      return out.sort((a, b) => b.releasedAt.localeCompare(a.releasedAt));
    case "populaires":
      return out.sort((a, b) => b.reviews - a.reviews);
    default:
      /* Relevance: in stock first, then new, then well reviewed. Sold-out items
         sinking to the bottom is worth more than any clever scoring. */
      return out.sort((a, b) => {
        const stock = Number(b.stock > 0) - Number(a.stock > 0);
        if (stock) return stock;
        const isNew = Number(b.isNew) - Number(a.isNew);
        if (isNew) return isNew;
        return b.reviews - a.reviews;
      });
  }
}

export function countActive(f: Filters) {
  return (
    f.club.length +
    f.pays.length +
    f.league.length +
    f.kit.length +
    f.saison.length +
    f.taille.length +
    f.category.length +
    (f.promo ? 1 : 0) +
    (f.enStock ? 1 : 0) +
    (f.prixMax !== null ? 1 : 0)
  );
}

/** Facet counts computed against everything *except* that facet's own
 *  selection, so a shopper can still see the other clubs after picking one. */
export function facetCounts(
  products: Product[],
  f: Filters,
  facet: keyof Filters,
  values: string[],
) {
  const base = applyFilters(products, { ...f, [facet]: [] } as Filters);
  return Object.fromEntries(
    values.map((v) => [
      v,
      base.filter((p) => {
        switch (facet) {
          case "club":
          case "pays":
            return p.teamSlug === v;
          case "league":
            return p.league === v;
          case "kit":
            return p.kit === v;
          case "saison":
            return p.season === v;
          case "category":
            return p.category === v;
          case "taille":
            return p.sizes.includes(v);
          default:
            return false;
        }
      }).length,
    ]),
  );
}
