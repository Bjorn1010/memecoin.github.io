import { cn } from "@/lib/utils";

type Tone = "sale" | "new" | "limited" | "soldout" | "neutral";

const tones: Record<Tone, string> = {
  /* Dark type on the red, not bone: black scores 5.7:1 against this red where
     white manages 2.9 and fails AA. */
  sale: "bg-sale text-void",
  /* "New" borrows the volt accent but never at full strength — the solid volt
     fill belongs to the primary CTA alone. */
  new: "bg-volt/15 text-volt border border-volt/30",
  limited: "bg-ink/10 text-steel-100 border border-ink/20 backdrop-blur-sm",
  soldout: "bg-steel-800 text-steel-400 border border-ink/10",
  neutral: "bg-void/70 text-steel-200 border border-line backdrop-blur-sm",
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
