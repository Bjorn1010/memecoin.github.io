import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Reveal } from "@/components/motion/Reveal";

/* Every section on the site opens the same way: an eyebrow, a display title,
 * and an optional link out. Consistency here is what makes the page scan as
 * one designed system rather than a stack of blocks. */

export function SectionHeader({
  eyebrow,
  title,
  description,
  href,
  linkLabel = "Tout voir",
}: {
  eyebrow: string;
  title: React.ReactNode;
  description?: string;
  href?: string;
  linkLabel?: string;
}) {
  return (
    <div className="mb-12 flex flex-wrap items-end justify-between gap-6">
      <div className="max-w-2xl">
        <Reveal>
          <p className="label-mono mb-4 flex items-center gap-3 text-volt">
            <span className="inline-block h-px w-8 bg-pitch" />
            {eyebrow}
          </p>
        </Reveal>
        <Reveal index={1}>
          <h2 className="font-display text-display text-ink">{title}</h2>
        </Reveal>
        {description && (
          <Reveal index={2}>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-steel-400">{description}</p>
          </Reveal>
        )}
      </div>

      {href && (
        <Reveal index={2}>
          <Link
            href={href}
            className="label-mono group flex items-center gap-2 border-b border-ink/20 pb-1 text-steel-200 transition-colors hover:border-volt hover:text-volt"
          >
            {linkLabel}
            <ArrowRight size={14} className="transition-transform group-hover:translate-x-1" />
          </Link>
        </Reveal>
      )}
    </div>
  );
}
