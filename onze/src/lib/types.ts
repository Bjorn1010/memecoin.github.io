export type Category =
  | "maillots"
  | "kits-enfants"
  | "retros"
  | "editions-speciales"
  | "survetements"
  | "vestes";

export type KitType = "domicile" | "exterieur" | "third" | "gardien" | "retro";

export type League =
  | "Premier League"
  | "La Liga"
  | "Serie A"
  | "Bundesliga"
  | "Ligue 1"
  | "Autres clubs"
  | "Sélections";

export type Confederation = "Europe" | "Amérique" | "Afrique" | "Asie" | "Océanie";

/** Jerseys are rendered procedurally from a colourway rather than shipped as
 *  photography, so no third-party imagery or club marks are used anywhere.
 *  Swap `Jersey` for real photography by replacing the component, not the data. */
export interface Colorway {
  primary: string;
  secondary: string;
  accent: string;
  pattern: "solid" | "stripes" | "hoops" | "sash" | "halves" | "gradient";
}

export interface Product {
  id: string;
  slug: string;
  name: string;
  team: string;
  teamSlug: string;
  league: League;
  confederation: Confederation;
  category: Category;
  kit: KitType;
  season: string;
  price: number;
  compareAt?: number;
  sizes: string[];
  colorway: Colorway;
  rating: number;
  reviews: number;
  stock: number;
  isNew: boolean;
  releasedAt: string;
  description: string;
}

export interface Team {
  name: string;
  slug: string;
  league: League;
  confederation: Confederation;
  colorway: Colorway;
  /** Two- or three-letter monogram standing in for a crest. Deliberately
   *  typographic — no club marks are reproduced. */
  monogram: string;
  founded: number;
}

export interface Collection {
  slug: string;
  title: string;
  tagline: string;
  category: Category | "nouveautes";
  accent: string;
  count: number;
}

export interface CartLine {
  productId: string;
  slug: string;
  name: string;
  team: string;
  size: string;
  price: number;
  quantity: number;
  colorway: Colorway;
}
