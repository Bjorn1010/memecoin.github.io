import Link from "next/link";
import { collections } from "@/lib/data/collections";
import { clubs, countries } from "@/lib/data/teams";

/* The newsletter lives in its own section directly above the footer, so there
 * is deliberately no second capture form down here — two email fields stacked
 * on top of each other is the fastest way to make a site feel like a template. */

const GROUPS = [
  {
    title: "Boutique",
    links: [
      { label: "Tous les maillots", href: "/maillots" },
      ...collections.slice(0, 5).map((c) => ({ label: c.title, href: `/collections/${c.slug}` })),
      { label: "Promotions", href: "/promotions" },
    ],
  },
  {
    title: "Clubs",
    links: [
      ...clubs.slice(0, 6).map((c) => ({ label: c.name, href: `/clubs/${c.slug}` })),
      { label: "Tous les clubs", href: "/clubs" },
    ],
  },
  {
    title: "Sélections",
    links: [
      ...countries.slice(0, 6).map((c) => ({ label: c.name, href: `/selections/${c.slug}` })),
      { label: "Toutes les sélections", href: "/selections" },
    ],
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
      { label: "Mentions légales", href: "/legal/mentions" },
      { label: "Confidentialité", href: "/legal/confidentialite" },
      { label: "CGV", href: "/legal/cgv" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="relative border-t border-line bg-base">
      <div className="mx-auto max-w-[1600px] px-5 py-16 lg:px-10">
        <div className="grid gap-12 lg:grid-cols-[1.2fr_repeat(5,1fr)]">
          <div className="max-w-xs">
            <p className="font-display text-3xl text-ink">
              ONZE<span className="text-volt">.</span>
            </p>
            <p className="mt-4 text-sm leading-relaxed text-steel-400">
              Maillots de football sélectionnés, floqués et expédiés depuis la Suisse.
            </p>
            <ul className="mt-8 flex gap-4">
              {["Instagram", "TikTok", "X"].map((network) => (
                <li key={network}>
                  {/* No account exists yet, so these are marked as such rather
                      than pointed at a profile that would 404. */}
                  <span
                    className="label-mono cursor-default text-steel-500"
                    title="Compte à créer"
                  >
                    {network}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {GROUPS.map((group) => (
            <nav key={group.title} aria-label={group.title}>
              <p className="label-mono mb-4 text-steel-500">{group.title}</p>
              <ul className="space-y-2.5">
                {group.links.map((l) => (
                  <li key={l.href + l.label}>
                    <Link
                      href={l.href}
                      className="text-sm text-steel-300 transition-colors hover:text-volt"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-16 flex flex-col gap-4 border-t border-line pt-8 text-xs text-steel-500 sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} ONZE. Tous droits réservés.</p>
          <p className="max-w-xl">
            Répliques non officielles. ONZE n&apos;est affilié à aucun club, fédération ou
            équipementier. Les noms d&apos;équipes sont cités à titre descriptif ; aucun écusson,
            logo ou marque n&apos;est reproduit.
          </p>
        </div>
      </div>
    </footer>
  );
}
