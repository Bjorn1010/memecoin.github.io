import type { MetadataRoute } from "next";
import { products } from "@/lib/data/products";
import { collections } from "@/lib/data/collections";
import { allTeams } from "@/lib/data/teams";

const BASE = "https://onze.example";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  const staticRoutes = ["", "/maillots", "/collections"].map((path) => ({
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

  /* Faceted club and country landing pages. These are the queries people
     actually search ("maillot arsenal"), so they get real sitemap entries
     rather than being left as filter state. */
  const teamRoutes = allTeams.map((t) => ({
    url: `${BASE}/maillots?${t.league === "Sélections" ? "pays" : "club"}=${t.slug}`,
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: 0.6,
  }));

  return [...staticRoutes, ...collectionRoutes, ...productRoutes, ...teamRoutes];
}
