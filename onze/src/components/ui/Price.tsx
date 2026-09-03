import { cn, discountPercent, formatPrice } from "@/lib/utils";

/* Tabular figures throughout, so prices in a grid align column-to-column
 * instead of jittering as digits change. */

export function Price({
  price,
  compareAt,
  size = "md",
  className,
}: {
  price: number;
  compareAt?: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const off = discountPercent(price, compareAt);

  const scale = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-2xl",
  }[size];

  return (
    <div className={cn("flex items-baseline gap-2", className)}>
      <span className={cn("tabular font-semibold", scale, off && "text-sale")}>
        {formatPrice(price)}
      </span>
      {compareAt && (
        <>
          <span className="tabular text-sm text-steel-500 line-through">
            {formatPrice(compareAt)}
          </span>
          {/* The percentage is announced to screen readers as a saving, not as
              a bare number floating next to two prices. */}
          <span className="sr-only">soit {off}% de réduction</span>
          <span aria-hidden className="label-mono text-sale">
            −{off}%
          </span>
        </>
      )}
    </div>
  );
}
