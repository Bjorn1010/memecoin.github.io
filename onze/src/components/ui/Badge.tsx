import { cn } from "@/lib/utils";

type Tone = "sale" | "new" | "limited" | "soldout" | "neutral";

const tones: Record<Tone, string> = {
  sale: "bg-sale text-ink",
  /* "New" borrows the volt accent but never at full strength — the solid volt
     fill belongs to the primary CTA alone. */
  new: "bg-pitch/15 text-pitch border border-pitch/30",
  limited: "bg-ink/10 text-steel-100 border border-ink/20 backdrop-blur-sm",
  soldout: "bg-steel-800 text-steel-400 border border-ink/10",
  neutral: "bg-ink/50 text-steel-200 border border-ink/10 backdrop-blur-sm",
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
