import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      /* Checkout and account carry no indexable content and would only bleed
         crawl budget away from product pages. */
      disallow: ["/checkout", "/compte", "/wishlist"],
    },
    sitemap: "https://onze.example/sitemap.xml",
  };
}
