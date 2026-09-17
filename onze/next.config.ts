import type { NextConfig } from "next";

/* Served from https://bjorn1010.github.io/memecoin.github.io/onze/.
 *
 * GitHub Pages only serves a repo at the bare domain root when the repo is
 * named exactly "<owner>.github.io". This repo is "memecoin.github.io" under
 * owner "Bjorn1010" — the names don't match, so it is a normal project repo
 * and Pages publishes it under its own repo name. The basePath has to include
 * that segment, or the built HTML links to /onze/... while the site actually
 * lives at /memecoin.github.io/onze/..., and every asset 404s.
 *
 * If the repo is ever renamed to "bjorn1010.github.io", switch this back to
 * "/onze" (and update the SITE/BASE constants in layout.tsx, sitemap.ts and
 * robots.ts to match) — that repo name makes GitHub treat it as the account's
 * root site instead. */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "/memecoin.github.io/onze";

/* Static export. Every route is prerendered to flat HTML so the shop can be
 * served by any static host — GitHub Pages included — with no Node runtime.
 *
 * This is possible because nothing here needs a server: the catalogue reads its
 * query parameters client-side, the cart lives in localStorage, and the product
 * pages come from generateStaticParams. */
const nextConfig: NextConfig = {
  output: "export",
  basePath,

  /* next/image's optimiser needs a server. The site ships no raster images —
   * jerseys are drawn as SVG and canvas — so there is nothing to optimise. */
  images: { unoptimized: true },

  /* Emit /maillots/index.html rather than /maillots.html, which is what static
   * hosts expect when serving clean URLs. */
  trailingSlash: true,
};

export default nextConfig;
