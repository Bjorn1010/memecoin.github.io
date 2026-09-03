import { cn } from "@/lib/utils";

type Tone = "sale" | "new" | "limited" | "soldout" | "neutral";

const tones: Record<Tone, string> = {
  sale: "bg-sale text-white",
  /* "New" borrows the volt accent but never at full strength — the solid volt
     fill belongs to the primary CTA alone. */
  new: "bg-volt/15 text-volt border border-volt/30",
  limited: "bg-white/10 text-steel-100 border border-white/20 backdrop-blur-sm",
  soldout: "bg-steel-800 text-steel-400 border border-white/10",
  neutral: "bg-black/50 text-steel-200 border border-white/10 backdrop-blur-sm",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "label-mono inline-flex items-center rounded-xs px-2 py-1 leading-none",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
