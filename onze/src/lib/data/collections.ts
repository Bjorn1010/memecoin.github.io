import type { Collection } from "@/lib/types";
import { countForCategory, products } from "@/lib/data/products";

/* Each collection carries its own accent so the grid reads as seven distinct
 * territories rather than one repeated card. Accents are used at low opacity
 * behind the card — the volt system accent stays reserved for CTAs. */

export const collections: Collection[] = [
  {
    slug: "nouveautes",
    title: "Nouveautés",
    tagline: "Les sorties 26/27, dès leur mise en ligne.",
    category: "nouveautes",
    accent: "#ccff00",
    count: products.filter((p) => p.isNew).length,
  },
  {
    slug: "maillots",
    title: "Maillots",
    tagline: "Domicile, extérieur, third. Toutes les grandes écuries.",
    category: "maillots",
    accent: "#4a7cff",
    count: countForCategory("maillots"),
  },
  {
    slug: "kits-enfants",
    title: "Kits enfants",
    tagline: "Maillot, short et chaussettes. Du 4 au 14 ans.",
    category: "kits-enfants",
    accent: "#ff8a3d",
    count: countForCategory("kits-enfants"),
  },
  {
    slug: "retros",
    title: "Rétros",
    tagline: "Les maillots qui ont écrit les nuits européennes.",
    category: "retros",
    accent: "#d4af37",
    count: countForCategory("retros"),
  },
  {
    slug: "editions-speciales",
    title: "Éditions spéciales",
    tagline: "Tirages limités, traitements blackout, finitions métallisées.",
    category: "editions-speciales",
    accent: "#b06cff",
    count: countForCategory("editions-speciales"),
  },
  {
    slug: "survetements",
    title: "Survêtements",
    tagline: "L'avant-match. Coupe ajustée, tissu technique.",
    category: "survetements",
    accent: "#2fd6a8",
    count: countForCategory("survetements"),
  },
  {
    slug: "vestes",
    title: "Vestes & pulls",
    tagline: "Le vestiaire hors du terrain.",
    category: "vestes",
    accent: "#ff4d6d",
    count: countForCategory("vestes"),
  },
];

export function collectionBySlug(slug: string) {
  return collections.find((c) => c.slug === slug);
}
