import type { NextConfig } from "next";

/* Served from https://bjorn1010.github.io/onze/ — a subdirectory of the Pages
 * site, so the repo root stays free for another project. Override with
 * NEXT_PUBLIC_BASE_PATH="" to build for a domain root instead. */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "/onze";

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
