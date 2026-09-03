import Link from "next/link";
import { collections } from "@/lib/data/collections";
import { clubs } from "@/lib/data/teams";

const GROUPS = [
  {
    title: "Boutique",
    links: collections.map((c) => ({ label: c.title, href: `/collections/${c.slug}` })),
  },
  {
    title: "Clubs",
    links: clubs.slice(0, 7).map((c) => ({ label: c.name, href: `/maillots?club=${c.slug}` })),
  },
  {
    title: "Aide",
    links: [
      { label: "Livraison & délais", href: "/aide/livraison" },
      { label: "Retours", href: "/aide/retours" },
      { label: "Guide des tailles", href: "/aide/tailles" },
      { label: "Flocage", href: "/aide/flocage" },
      { label: "Nous contacter", href: "/aide/contact" },
    ],
  },
  {
    title: "Maison",
    links: [
      { label: "À propos", href: "/a-propos" },
      { label: "Mentions légales", href: "/legal" },
      { label: "Confidentialité", href: "/legal/confidentialite" },
      { label: "CGV", href: "/legal/cgv" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="relative mt-32 border-t border-white/8 bg-base">
      <div className="mx-auto max-w-[1600px] px-5 py-16 lg:px-10">
        <div className="grid gap-12 lg:grid-cols-[1.4fr_repeat(4,1fr)]">
          <div className="max-w-sm">
            <p className="font-display text-3xl text-white">
              ONZE<span className="text-volt">.</span>
            </p>
            <p className="mt-4 text-sm leading-relaxed text-steel-400">
              Maillots de football sélectionnés, floqués et expédiés depuis la Suisse.
              Nouveautés chaque semaine.
            </p>

            <form className="mt-8" action="/newsletter" method="post">
              <label htmlFor="newsletter" className="label-mono text-steel-500">
                Nouveautés en avant-première
              </label>
              <div className="mt-3 flex gap-2">
                <input
                  id="newsletter"
                  name="email"
                  type="email"
                  required
                  placeholder="vous@exemple.ch"
                  className="h-11 min-w-0 flex-1 rounded-sm border border-white/12 bg-surface px-3 text-sm text-white outline-none transition-colors placeholder:text-steel-600 focus:border-volt/60"
                />
                <button
                  type="submit"
                  className="label-mono h-11 shrink-0 rounded-sm bg-steel-100 px-5 text-void transition-colors hover:bg-white"
                >
                  OK
                </button>
              </div>
            </form>
          </div>

          {GROUPS.map((group) => (
            <nav key={group.title} aria-label={group.title}>
              <p className="label-mono mb-4 text-steel-500">{group.title}</p>
              <ul className="space-y-2.5">
                {group.links.map((l) => (
                  <li key={l.href + l.label}>
                    <Link
                      href={l.href}
                      className="text-sm text-steel-300 transition-colors hover:text-white"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-16 flex flex-col gap-4 border-t border-white/8 pt-8 text-xs text-steel-500 sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} ONZE. Tous droits réservés.</p>
          <p className="max-w-xl">
            Répliques non officielles. ONZE n&apos;est affilié à aucun club, fédération ou
            équipementier. Les noms d&apos;équipes sont cités à titre descriptif.
          </p>
        </div>
      </div>
    </footer>
  );
}
