import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { collections } from "@/lib/data/collections";
import { Reveal } from "@/components/motion/Reveal";

export const metadata: Metadata = {
  title: "Collections",
  description:
    "Nouveautés, maillots, kits enfants, rétros, éditions spéciales, survêtements et vestes.",
  alternates: { canonical: "/collections" },
};

export default function CollectionsPage() {
  return (
    <div className="mx-auto max-w-[1600px] px-5 pt-32 lg:px-10">
      <header className="mb-14">
        <p className="label-mono mb-4 flex items-center gap-3 text-volt">
          <span className="inline-block h-px w-8 bg-volt" />
          Le vestiaire
        </p>
        <h1 className="font-display text-display text-white">Collections</h1>
        <p className="mt-4 max-w-md text-sm leading-relaxed text-steel-400">
          Sept territoires, chacun avec sa propre identité.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {collections.map((c, i) => (
          <Reveal key={c.slug} index={i} as="div">
            <Link
              href={`/collections/${c.slug}`}
              className="group relative flex min-h-[260px] flex-col justify-between overflow-hidden rounded-xl border border-white/8 bg-surface p-7 transition-colors hover:border-white/20"
            >
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-30 transition-all duration-[--duration-premium] ease-[--ease-out-expo] group-hover:scale-110 group-hover:opacity-60"
                style={{
                  background: `radial-gradient(70% 60% at 20% 100%, ${c.accent}66, transparent 70%)`,
                }}
              />
              <div className="relative flex items-start justify-between gap-4">
                <h2 className="font-display text-2xl uppercase text-white">{c.title}</h2>
                <ArrowUpRight
                  size={18}
                  className="mt-1 shrink-0 text-steel-500 transition-all group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-volt"
                />
              </div>
              <div className="relative">
                <p className="max-w-xs text-sm leading-relaxed text-steel-400">{c.tagline}</p>
                <p className="scoreboard mt-4 text-2xl text-steel-600">{c.count}</p>
              </div>
            </Link>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
