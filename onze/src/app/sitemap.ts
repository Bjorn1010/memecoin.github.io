import type { MetadataRoute } from "next";
import { products } from "@/lib/data/products";
import { collections } from "@/lib/data/collections";
import { clubs, countries } from "@/lib/data/teams";

/* Static export needs this declared explicitly: the route has no dynamic
   inputs, but Next will not assume that. */
export const dynamic = "force-static";

/* Kept in sync with next.config.ts's basePath — see the comment there for why
   the path includes the repo name. */
const BASE = "https://bjorn1010.github.io/memecoin.github.io/onze";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  const staticRoutes = [
    "",
    "/maillots",
    "/collections",
    "/clubs",
    "/selections",
    "/promotions",
  ].map((path) => ({
    url: `${BASE}${path}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: path === "" ? 1 : 0.9,
  }));

  const collectionRoutes = collections.map((c) => ({
    url: `${BASE}/collections/${c.slug}`,
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  const productRoutes = products.map((p) => ({
    url: `${BASE}/produit/${p.slug}`,
    lastModified: new Date(p.releasedAt),
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));

  /* Club and country landing pages. These are the queries people actually
     search ("maillot arsenal"), and they are now real prerendered routes with
     their own <h1> and metadata — so the sitemap points at those rather than
     at a filtered /maillots?club= URL, which is a worse thing to index and
     competes with the page that should rank. */
  const teamRoutes = [
    ...clubs.map((t) => `${BASE}/clubs/${t.slug}`),
    ...countries.map((t) => `${BASE}/selections/${t.slug}`),
  ].map((url) => ({
    url,
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: 0.6,
  }));

  return [...staticRoutes, ...collectionRoutes, ...productRoutes, ...teamRoutes];
}
