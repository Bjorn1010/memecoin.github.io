import type { Category, KitType, Product } from "@/lib/types";
import { allTeams, clubs, countries } from "@/lib/data/teams";

/* Products are derived deterministically from the team table rather than hand
 * written. Same catalogue on server and client, no hydration drift, and adding
 * a team automatically yields its kits. Swap this module for a real commerce
 * API — everything downstream consumes the `Product` type, not this file. */

/** Cheap deterministic hash so "random-looking" values stay stable per slug. */
function seed(input: string) {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

function pick<T>(key: string, options: readonly T[]) {
  return options[seed(key) % options.length];
}

const SIZES = ["S", "M", "L", "XL", "XXL"];
const KID_SIZES = ["4A", "6A", "8A", "10A", "12A", "14A"];

const KIT_LABEL: Record<KitType, string> = {
  domicile: "Domicile",
  exterieur: "Extérieur",
  third: "Third",
  gardien: "Gardien",
  retro: "Rétro",
};

function describe(team: string, kit: KitType, season: string) {
  return [
    `Maillot ${team} ${KIT_LABEL[kit].toLowerCase()} saison ${season}.`,
    "Coupe supporter, maille technique respirante à séchage rapide,",
    "col côtelé et finitions thermocollées. Flocage nom et numéro inclus.",
  ].join(" ");
}

/** Away kits are recoloured from the home colourway rather than invented, so a
 *  club still reads as itself across its kits. */
function deriveColorway(team: (typeof allTeams)[number], kit: KitType) {
  const { primary, secondary, accent, pattern } = team.colorway;
  switch (kit) {
    case "exterieur":
      return { primary: secondary, secondary: primary, accent, pattern };
    case "third":
      return { primary: "#12121a", secondary: accent, accent: primary, pattern: "gradient" as const };
    case "retro":
      return { primary, secondary, accent, pattern: pattern === "solid" ? ("hoops" as const) : pattern };
    default:
      return team.colorway;
  }
}

function buildProduct(
  team: (typeof allTeams)[number],
  kit: KitType,
  category: Category,
  season: string,
): Product {
  const key = `${team.slug}-${kit}-${category}-${season}`;
  const s = seed(key);

  const base = category === "kits-enfants" ? 44 : category === "retros" ? 79 : 89;
  const price = base + (s % 7) * 5;
  /* Roughly a third of the catalogue carries a markdown. */
  const onSale = s % 3 === 0;
  const compareAt = onSale ? Math.round(price * (1.25 + (s % 4) * 0.08)) : undefined;

  const slug = `${team.slug}-${kit}-${season.replace("/", "-")}${
    category === "kits-enfants" ? "-enfant" : category === "retros" ? "-retro" : ""
  }`;

  return {
    id: `p-${s.toString(36)}`,
    slug,
    name: `${team.name} ${KIT_LABEL[kit]} ${season}`,
    team: team.name,
    teamSlug: team.slug,
    league: team.league,
    confederation: team.confederation,
    category,
    kit,
    season,
    price,
    compareAt,
    sizes: category === "kits-enfants" ? KID_SIZES : SIZES,
    colorway: deriveColorway(team, kit),
    rating: 4 + ((s % 10) / 10),
    reviews: 12 + (s % 240),
    stock: s % 11 === 0 ? 0 : 3 + (s % 40),
    isNew: category !== "retros" && s % 4 === 0,
    releasedAt: `2026-0${1 + (s % 9)}-1${s % 10}`,
    description: describe(team.name, kit, season),
  };
}

const CURRENT = "26/27";
const RETRO_SEASONS = ["98/99", "02/03", "06/07", "10/11"] as const;

function buildCatalogue(): Product[] {
  const out: Product[] = [];

  /* Current-season kits for every club and country. */
  for (const team of allTeams) {
    out.push(buildProduct(team, "domicile", "maillots", CURRENT));
    out.push(buildProduct(team, "exterieur", "maillots", CURRENT));
    /* Only the larger teams get a third kit — mirrors how real ranges work. */
    if (seed(team.slug) % 2 === 0) {
      out.push(buildProduct(team, "third", "maillots", CURRENT));
    }
  }

  /* Children's kits for the most requested clubs and countries. */
  for (const team of [...clubs.slice(0, 10), ...countries.slice(0, 8)]) {
    out.push(buildProduct(team, "domicile", "kits-enfants", CURRENT));
  }

  /* Retros, one per historic club. */
  for (const team of clubs) {
    if (seed(`retro-${team.slug}`) % 2 !== 0) continue;
    const season = pick(`season-${team.slug}`, RETRO_SEASONS);
    out.push(buildProduct(team, "retro", "retros", season));
  }

  /* Special editions — blacked-out treatments over the club accent. */
  for (const team of clubs.slice(0, 8)) {
    const p = buildProduct(team, "third", "editions-speciales", CURRENT);
    out.push({
      ...p,
      slug: `${team.slug}-edition-speciale-${CURRENT.replace("/", "-")}`,
      name: `${team.name} Édition Spéciale ${CURRENT}`,
      price: p.price + 30,
      colorway: { primary: "#0b0b0f", secondary: team.colorway.primary, accent: "#ccff00", pattern: "gradient" },
      description: `Édition spéciale ${team.name}, tirage limité. Traitement blackout, détails métallisés et flocage or.`,
    });
  }

  /* Tracksuits and outerwear, priced above jerseys. */
  for (const team of clubs.slice(0, 12)) {
    const isJacket = seed(`jacket-${team.slug}`) % 2 === 0;
    const p = buildProduct(team, "domicile", isJacket ? "vestes" : "survetements", CURRENT);
    out.push({
      ...p,
      slug: `${team.slug}-${isJacket ? "veste" : "survetement"}-${CURRENT.replace("/", "-")}`,
      name: `${team.name} ${isJacket ? "Veste" : "Survêtement"} ${CURRENT}`,
      price: p.price + (isJacket ? 40 : 55),
      description: `${isJacket ? "Veste" : "Survêtement"} d'entraînement ${team.name}, coupe ajustée, tissu technique déperlant.`,
    });
  }

  return out;
}

export const products: Product[] = buildCatalogue();

export const productsBySlug = new Map(products.map((p) => [p.slug, p]));

export function getProduct(slug: string) {
  return productsBySlug.get(slug);
}

export function newArrivals(limit = 8) {
  return products
    .filter((p) => p.isNew)
    .sort((a, b) => b.releasedAt.localeCompare(a.releasedAt))
    .slice(0, limit);
}

export function bestSellers(limit = 8) {
  return [...products].sort((a, b) => b.reviews - a.reviews).slice(0, limit);
}

export function onSale(limit = 8) {
  return products
    .filter((p) => p.compareAt)
    .sort((a, b) => (b.compareAt! - b.price) / b.compareAt! - (a.compareAt! - a.price) / a.compareAt!)
    .slice(0, limit);
}

export function relatedTo(product: Product, limit = 4) {
  const sameTeam = products.filter((p) => p.teamSlug === product.teamSlug && p.slug !== product.slug);
  const sameLeague = products.filter(
    (p) => p.league === product.league && p.teamSlug !== product.teamSlug,
  );
  return [...sameTeam, ...sameLeague].slice(0, limit);
}

export function countForTeam(slug: string) {
  return products.filter((p) => p.teamSlug === slug).length;
}

export function countForCategory(category: Category) {
  return products.filter((p) => p.category === category).length;
}

export const priceBounds = products.reduce(
  (acc, p) => ({ min: Math.min(acc.min, p.price), max: Math.max(acc.max, p.price) }),
  { min: Infinity, max: 0 },
);

export const seasons = [...new Set(products.map((p) => p.season))].sort().reverse();
export const allSizes = [...new Set(products.flatMap((p) => p.sizes))];
