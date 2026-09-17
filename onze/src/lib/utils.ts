import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Swiss francs, the reference market. Non-breaking space before the unit. */
export function formatPrice(value: number) {
  return new Intl.NumberFormat("fr-CH", {
    style: "currency",
    currency: "CHF",
    minimumFractionDigits: 2,
  }).format(value);
}

export function discountPercent(price: number, compareAt?: number) {
  if (!compareAt || compareAt <= price) return null;
  return Math.round((1 - price / compareAt) * 100);
}

export function slugify(input: string) {
  return input
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

/* The site is served from a subdirectory on GitHub Pages. next/link and
 * next/image prefix that themselves; a plain <img src> does not, so anything
 * pointing at /public has to go through here or it 404s in production while
 * working perfectly in dev. Kept in sync with next.config.ts's basePath. */
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "/memecoin.github.io/onze";

export function asset(path: string) {
  return `${BASE_PATH}${path}`;
}
