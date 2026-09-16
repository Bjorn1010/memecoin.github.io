import { asset, cn } from "@/lib/utils";

/* Responsive photography for a statically exported site.
 *
 * next/image's optimiser needs a server, so the widths are generated ahead of
 * time (see the WebP set in /public/img) and handed to the browser as a plain
 * srcset. That keeps the one thing that actually matters on a photo-led page:
 * a phone downloads the 640px file, not the 1600px one.
 *
 * width/height are always set so the browser reserves the box before the
 * bytes arrive — on a page this image-heavy, layout shift is the difference
 * between premium and cheap. */

const WIDTHS = [640, 1024, 1600] as const;

const RATIO = {
  "16/9": 9 / 16,
  "4/5": 5 / 4,
} as const;

export function Img({
  name,
  alt,
  ratio = "16/9",
  sizes = "100vw",
  priority = false,
  className,
}: {
  name: string;
  /** Empty string marks the image as decorative, which is correct for the
      atmosphere photography behind a heading that already says the same thing. */
  alt: string;
  ratio?: keyof typeof RATIO;
  sizes?: string;
  priority?: boolean;
  className?: string;
}) {
  const base = 1024;
  return (
    <img
      src={asset(`/img/${name}-${base}.webp`)}
      srcSet={WIDTHS.map((w) => `${asset(`/img/${name}-${w}.webp`)} ${w}w`).join(", ")}
      sizes={sizes}
      alt={alt}
      aria-hidden={alt === "" || undefined}
      width={base}
      height={Math.round(base * RATIO[ratio])}
      loading={priority ? "eager" : "lazy"}
      fetchPriority={priority ? "high" : undefined}
      decoding="async"
      className={cn("h-full w-full object-cover", className)}
    />
  );
}
