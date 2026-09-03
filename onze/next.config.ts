import type { NextConfig } from "next";

/* Static export. Every route is prerendered to flat HTML so the shop can be
 * served by any static host — GitHub Pages included — with no Node runtime.
 *
 * This is possible because nothing here needs a server: the catalogue reads its
 * query parameters client-side, the cart lives in localStorage, and the product
 * pages come from generateStaticParams. */
const nextConfig: NextConfig = {
  output: "export",

  /* next/image's optimiser needs a server. The site ships no raster images —
   * jerseys are drawn as SVG and canvas — so there is nothing to optimise. */
  images: { unoptimized: true },

  /* Emit /maillots/index.html rather than /maillots.html, which is what static
   * hosts expect when serving clean URLs. */
  trailingSlash: true,
};

export default nextConfig;
