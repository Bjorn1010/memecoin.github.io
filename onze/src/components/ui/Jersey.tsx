import type { Colorway } from "@/lib/types";
import { cn } from "@/lib/utils";

/* Jerseys are drawn, not photographed. Every kit in the catalogue renders from
 * its colourway, which keeps the build free of third-party imagery and licensed
 * club marks, ships nothing over the wire, and scales to any size without a
 * CDN. Replace this component with real photography and the rest of the site
 * is unaffected — nothing else knows how a jersey is drawn. */

interface JerseyProps {
  colorway: Colorway;
  /** Typographic stand-in for a crest. Never a real club mark. */
  monogram?: string;
  number?: string;
  className?: string;
  /** Adds the rim light and contact shadow. Off for dense grids. */
  detailed?: boolean;
  /** Back view drives the flocage preview: arched name over a large number. */
  view?: "front" | "back";
  /** Player name printed above the number, back view only. */
  playerName?: string;
}

/* The torso outline, reused as both the fill shape and the clip path so
   patterns can never bleed past the garment edge. */
const BODY =
  "M100 26 L143 12 C152 9 160 13 168 20 L214 58 C220 63 220 71 215 77 L192 104 C188 109 181 109 177 105 L168 96 L168 236 C168 244 162 250 154 250 L46 250 C38 250 32 244 32 236 L32 96 L23 105 C19 109 12 109 8 104 L-15 77 C-20 71 -20 63 -14 58 L32 20 C40 13 48 9 57 12 L100 26 Z";

export function Jersey({
  colorway,
  monogram,
  number,
  className,
  detailed = true,
  view = "front",
  playerName,
}: JerseyProps) {
  const { primary, secondary, accent, pattern } = colorway;
  /* Ids must be unique per instance or multiple jerseys on one page share
     gradients and clip paths. */
  const uid = `${primary}${secondary}${pattern}${view}`.replace(/[^a-z0-9]/gi, "");
  const isBack = view === "back";

  return (
    <svg
      viewBox="-20 0 240 260"
      className={cn("h-full w-full", className)}
      role="img"
      aria-label={`Maillot ${pattern}`}
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <clipPath id={`clip-${uid}`}>
          <path d={BODY} />
        </clipPath>

        {/* Fabric shading: a soft vertical falloff plus a directional highlight,
            which is what stops a flat fill from reading as a paper cut-out. */}
        <linearGradient id={`shade-${uid}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.22" />
          <stop offset="42%" stopColor="#fff" stopOpacity="0.02" />
          <stop offset="100%" stopColor="#000" stopOpacity="0.4" />
        </linearGradient>

        <radialGradient id={`sheen-${uid}`} cx="0.32" cy="0.2" r="0.7">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#fff" stopOpacity="0" />
        </radialGradient>

        <linearGradient id={`grad-${uid}`} x1="0" y1="0" x2="0.6" y2="1">
          <stop offset="0%" stopColor={primary} />
          <stop offset="100%" stopColor={secondary} />
        </linearGradient>

        <pattern
          id={`stripes-${uid}`}
          width="32"
          height="8"
          patternUnits="userSpaceOnUse"
        >
          <rect width="32" height="8" fill={primary} />
          <rect width="16" height="8" fill={secondary} />
        </pattern>

        <pattern id={`hoops-${uid}`} width="8" height="48" patternUnits="userSpaceOnUse">
          <rect width="8" height="48" fill={primary} />
          <rect width="8" height="24" fill={secondary} />
        </pattern>
      </defs>

      <g clipPath={`url(#clip-${uid})`}>
        {/* Base fill — the pattern decides what the garment is made of. */}
        {pattern === "stripes" && <rect x="-20" y="0" width="240" height="260" fill={`url(#stripes-${uid})`} />}
        {pattern === "hoops" && <rect x="-20" y="0" width="240" height="260" fill={`url(#hoops-${uid})`} />}
        {pattern === "gradient" && <rect x="-20" y="0" width="240" height="260" fill={`url(#grad-${uid})`} />}
        {pattern === "halves" && (
          <>
            <rect x="-20" y="0" width="120" height="260" fill={primary} />
            <rect x="100" y="0" width="120" height="260" fill={secondary} />
          </>
        )}
        {pattern === "sash" && (
          <>
            <rect x="-20" y="0" width="240" height="260" fill={primary} />
            <path d="M-20 190 L200 30 L200 92 L-20 252 Z" fill={secondary} />
          </>
        )}
        {pattern === "solid" && <rect x="-20" y="0" width="240" height="260" fill={primary} />}

        {/* Shading stack, applied over whatever the pattern painted. */}
        <rect x="-20" y="0" width="240" height="260" fill={`url(#shade-${uid})`} />
        <rect x="-20" y="0" width="240" height="260" fill={`url(#sheen-${uid})`} />

        {/* Sleeve cuffs and hem in the accent — the detail that reads as "kit"
            rather than "t-shirt". */}
        <rect x="-16" y="86" width="52" height="9" fill={accent} opacity="0.9" />
        <rect x="164" y="86" width="52" height="9" fill={accent} opacity="0.9" />
        <rect x="32" y="240" width="136" height="6" fill={accent} opacity="0.55" />

        {/* Body seams. Very low opacity — they should register only up close. */}
        <path d="M68 96 L68 250 M132 96 L132 250" stroke="#000" strokeOpacity="0.12" strokeWidth="1" />
      </g>

      {/* Collar sits outside the clip so it can overhang the neckline. The back
          of a shirt has a shallow band, not the deep V of the front — drawing
          the front shape on both made the back read as a hood. */}
      {isBack ? (
        <path
          d="M100 24 L57 12 C68 22 82 28 100 28 C118 28 132 22 143 12 Z"
          fill={accent}
          opacity="0.92"
        />
      ) : (
        <>
          <path
            d="M100 26 L57 12 C66 30 82 42 100 42 C118 42 134 30 143 12 Z"
            fill={accent}
            opacity="0.92"
          />
          <path
            d="M100 42 C82 42 66 30 57 12"
            fill="none"
            stroke="#000"
            strokeOpacity="0.2"
            strokeWidth="1.5"
          />
        </>
      )}

      {/* FRONT — crest stand-in, small chest number. */}
      {!isBack && monogram && (
        <text
          x="138"
          y="86"
          textAnchor="middle"
          className="font-display"
          fontSize="15"
          fontWeight="800"
          letterSpacing="0.5"
          fill={accent}
          opacity="0.95"
        >
          {monogram}
        </text>
      )}
      {!isBack && number && (
        <text
          x="100"
          y="192"
          textAnchor="middle"
          className="font-display"
          fontSize="76"
          fontWeight="800"
          fill={accent}
          opacity="0.28"
        >
          {number}
        </text>
      )}

      {/* BACK — the flocage. Name arches over the number the way it is actually
          heat-pressed onto a shirt; the number is full-strength here because on
          the back it *is* the graphic. */}
      {isBack && (
        <>
          <defs>
            <path id={`arc-${uid}`} d="M44 118 Q100 96 156 118" fill="none" />
          </defs>
          {playerName && (
            <text
              className="font-display"
              fontSize="19"
              fontWeight="800"
              letterSpacing="1.5"
              fill={accent}
              textAnchor="middle"
            >
              <textPath href={`#arc-${uid}`} startOffset="50%">
                {playerName.toUpperCase().slice(0, 12)}
              </textPath>
            </text>
          )}
          {number && (
            <text
              x="100"
              y={playerName ? 212 : 200}
              textAnchor="middle"
              className="font-display"
              fontSize="98"
              fontWeight="800"
              fill={accent}
              stroke={primary}
              strokeWidth="1.5"
              paintOrder="stroke"
            >
              {number.slice(0, 2)}
            </text>
          )}
        </>
      )}

      {detailed && (
        <>
          {/* Rim light along the left shoulder, matching the CSS `edge-lit`
              treatment used on surfaces elsewhere. */}
          <path
            d={BODY}
            fill="none"
            stroke="#fff"
            strokeOpacity="0.16"
            strokeWidth="1.5"
          />
          <ellipse cx="100" cy="256" rx="70" ry="6" fill="#000" opacity="0.45" />
        </>
      )}
    </svg>
  );
}
