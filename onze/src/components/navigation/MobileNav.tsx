"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ChevronRight, X } from "lucide-react";
import { clubs, countries } from "@/lib/data/teams";
import { collections } from "@/lib/data/collections";
import { transition, spring } from "@/lib/motion";

/* Fullscreen mobile menu. Two levels: root sections, then a drill-down that
 * slides in. Keeps the thumb in one place instead of nesting accordions. */

type Panel = { title: string; items: { label: string; href: string }[] } | null;

const ROOT = [
  { label: "Nouveautés", href: "/collections/nouveautes" },
  { label: "Maillots", panel: "clubs" },
  { label: "Sélections", panel: "pays" },
  { label: "Collections", panel: "collections" },
  { label: "Kits enfants", href: "/collections/kits-enfants" },
  { label: "Rétros", href: "/collections/retros" },
  { label: "Survêtements", href: "/collections/survetements" },
  { label: "Vestes & pulls", href: "/collections/vestes" },
] as const;

export function MobileNav({ onClose }: { onClose: () => void }) {
  const [panel, setPanel] = useState<Panel>(null);

  /* Lock the page behind the sheet, and restore on unmount. */
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const openPanel = (key: string) => {
    if (key === "clubs")
      setPanel({
        title: "Clubs",
        items: clubs.map((c) => ({ label: c.name, href: `/maillots?club=${c.slug}` })),
      });
    if (key === "pays")
      setPanel({
        title: "Sélections",
        items: countries.map((c) => ({ label: c.name, href: `/maillots?pays=${c.slug}` })),
      });
    if (key === "collections")
      setPanel({
        title: "Collections",
        items: collections.map((c) => ({ label: c.title, href: `/collections/${c.slug}` })),
      });
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={transition.fast}
      className="fixed inset-0 z-[70] bg-void lg:hidden"
      role="dialog"
      aria-modal="true"
      aria-label="Menu principal"
    >
      <div className="flex h-16 items-center justify-between px-5">
        <span className="font-display text-xl text-white">
          ONZE<span className="text-volt">.</span>
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer le menu"
          className="-mr-2 grid h-10 w-10 place-items-center text-steel-200"
        >
          <X size={24} strokeWidth={1.75} />
        </button>
      </div>

      <div className="relative h-[calc(100dvh-4rem)] overflow-hidden">
        {/* Root list */}
        <motion.nav
          animate={{ x: panel ? "-32%" : 0, opacity: panel ? 0.25 : 1 }}
          transition={spring.panel}
          className="h-full overflow-y-auto px-5 pb-16"
        >
          {ROOT.map((item, i) => (
            <motion.div
              key={item.label}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ ...transition.standard, delay: 0.03 * i }}
            >
              {"href" in item ? (
                <Link
                  href={item.href}
                  onClick={onClose}
                  className="flex items-center justify-between border-b border-white/6 py-5 font-display text-2xl uppercase text-white"
                >
                  {item.label}
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => openPanel(item.panel)}
                  className="flex w-full items-center justify-between border-b border-white/6 py-5 font-display text-2xl uppercase text-white"
                >
                  {item.label}
                  <ChevronRight size={22} className="text-steel-500" />
                </button>
              )}
            </motion.div>
          ))}

          <div className="mt-8 flex gap-3">
            <Link
              href="/compte"
              onClick={onClose}
              className="label-mono flex-1 rounded-sm border border-white/15 py-3 text-center text-steel-200"
            >
              Compte
            </Link>
            <Link
              href="/wishlist"
              onClick={onClose}
              className="label-mono flex-1 rounded-sm border border-white/15 py-3 text-center text-steel-200"
            >
              Wishlist
            </Link>
          </div>
        </motion.nav>

        {/* Drill-down */}
        {panel && (
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={spring.panel}
            className="absolute inset-0 overflow-y-auto bg-void px-5 pb-16"
          >
            <button
              type="button"
              onClick={() => setPanel(null)}
              className="label-mono flex items-center gap-2 py-5 text-steel-400"
            >
              <ChevronRight size={16} className="rotate-180" />
              Retour
            </button>
            <p className="mb-4 font-display text-3xl uppercase text-white">{panel.title}</p>
            {panel.items.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className="block border-b border-white/6 py-4 text-lg text-steel-200"
              >
                {item.label}
              </Link>
            ))}
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
