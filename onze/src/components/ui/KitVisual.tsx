import type { Colorway } from "@/lib/types";
import { Jersey } from "@/components/ui/Jersey";
import { cn } from "@/lib/utils";

/* The seam between drawn kits and real photography.
 *
 * Everything in the storefront renders its kit through this component, so
 * switching a product from a drawn jersey to a real photograph is a matter of
 * putting a `photo` on it — nothing else in the codebase has to change.
 *
 * Why the catalogue ships drawn by default: real kit photography and club
 * crests are someone else's copyright and trademarks, and a shop selling
 * unofficial replicas is the worst possible place to be caught reusing them.
 * Supply your own product shots — or images you have licensed — and they take
 * over automatically.
 *
 * Drop files in /public/kits/ and set photo: "/kits/barcelona-home-2627.webp".
 */

interface KitVisualProps {
  colorway: Colorway;
  /** Path or URL to real product photography. Takes precedence when present. */
  photo?: string;
  alt: string;
  monogram?: string;
  number?: string;
  view?: "front" | "back";
  playerName?: string;
  className?: string;
  detailed?: boolean;
  /** Photos above the fold should not lazy-load; grids below it should. */
  priority?: boolean;
}

export function KitVisual({
  colorway,
  photo,
  alt,
  monogram,
  number,
  view = "front",
  playerName,
  className,
  detailed = true,
  priority = false,
}: KitVisualProps) {
  if (photo) {
    return (
      /* A plain <img>: the export runs with images.unoptimized, so next/image
         would add a wrapper and no optimisation. */
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={photo}
        alt={alt}
        className={cn("h-full w-full object-contain", className)}
        loading={priority ? "eager" : "lazy"}
        decoding="async"
      />
    );
  }

  return (
    <Jersey
      colorway={colorway}
      monogram={monogram}
      number={number}
      view={view}
      playerName={playerName}
      className={className}
      detailed={detailed}
    />
  );
}
