import Link from "next/link";
import type { StaticPage } from "@/lib/data/pages";
import { Reveal } from "@/components/motion/Reveal";

/* Shared editorial layout for help and legal pages. Narrow measure, generous
 * leading — these are the pages people read when something has gone wrong, so
 * legibility beats art direction. */

export function ArticlePage({
  page,
  breadcrumb,
}: {
  page: StaticPage;
  breadcrumb: { label: string; href: string };
}) {
  return (
    <article className="mx-auto max-w-2xl px-5 pt-32 pb-24">
      <nav aria-label="Fil d'Ariane" className="label-mono mb-8 flex gap-2 text-steel-600">
        <Link href="/" className="hover:text-ink">
          Accueil
        </Link>
        <span aria-hidden>/</span>
        <Link href={breadcrumb.href} className="hover:text-ink">
          {breadcrumb.label}
        </Link>
      </nav>

      <h1 className="font-display text-title text-ink">{page.title}</h1>
      <p className="mt-4 text-base leading-relaxed text-steel-300">{page.intro}</p>

      <div className="mt-14 space-y-12">
        {page.sections.map((section, i) => (
          <Reveal key={section.heading} index={i} as="section">
            <h2 className="label-mono mb-4 text-pitch">{section.heading}</h2>
            <div className="space-y-4">
              {section.body.map((paragraph) => (
                <p key={paragraph.slice(0, 24)} className="text-sm leading-[1.75] text-steel-300">
                  {paragraph}
                </p>
              ))}
            </div>
          </Reveal>
        ))}
      </div>
    </article>
  );
}
