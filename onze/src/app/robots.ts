import type { MetadataRoute } from "next";

/* Static export needs this declared explicitly: the route has no dynamic
   inputs, but Next will not assume that. */
export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      /* Checkout and account carry no indexable content and would only bleed
         crawl budget away from product pages. */
      disallow: ["/checkout", "/panier", "/compte", "/wishlist"],
    },
    /* Kept in sync with next.config.ts's basePath — see the comment there for
       why the path includes the repo name. */
    sitemap: "https://bjorn1010.github.io/memecoin.github.io/onze/sitemap.xml",
  };
}
