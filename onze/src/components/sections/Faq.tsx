"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { transition } from "@/lib/motion";

const ITEMS = [
  {
    q: "Les maillots sont-ils authentiques ?",
    a: "Oui. Toutes nos références sont sous licence officielle des clubs et fédérations, produites par les mêmes fournisseurs que les boutiques officielles.",
  },
  {
    q: "Le flocage nom et numéro est-il vraiment inclus ?",
    a: "Oui, sans supplément sur la quasi-totalité du catalogue. Le nom et le numéro se choisissent librement sur la fiche produit avant l'ajout au panier.",
  },
  {
    q: "Quels sont les délais de livraison ?",
    a: "Expédition sous 48 h ouvrables depuis la Suisse. Comptez 2 à 4 jours en Suisse et 4 à 8 jours pour le reste de l'Europe.",
  },
  {
    q: "Quelle est votre politique de retour ?",
    a: "30 jours à compter de la réception, article non porté et étiquette attachée. Les articles floqués sur mesure ne sont pas repris, le flocage étant réalisé spécifiquement pour vous.",
  },
  {
    q: "Comment choisir la bonne taille ?",
    a: "Chaque fiche produit indique la coupe (ajustée ou classique) et un guide des tailles en centimètres. En cas de doute entre deux tailles, l'équipe support répond sous 24 h.",
  },
  {
    q: "Les maillots rétro sont-ils d'époque ou des rééditions ?",
    a: "Ce sont des rééditions sous licence, neuves, pas des archives usagées. Même coupe et mêmes couleurs que le maillot d'origine, coutures actuelles.",
  },
  {
    q: "Quels moyens de paiement acceptez-vous ?",
    a: "Cartes bancaires principales et paiement en 3 fois sans frais. Transaction chiffrée de bout en bout, aucune donnée de carte n'est stockée sur nos serveurs.",
  },
  {
    q: "Proposez-vous des tailles enfant ?",
    a: "Oui, du 4 au 14 ans sur la majorité des références clubs et sélections, avec le même flocage inclus que sur les tailles adulte.",
  },
];

export function Faq() {
  return (
    <div className="border-t border-line">
      {ITEMS.map((item, i) => (
        <Item key={item.q} {...item} defaultOpen={i === 0} />
      ))}
    </div>
  );
}

function Item({ q, a, defaultOpen }: { q: string; a: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={reduced ? undefined : { opacity: 0, y: 16 }}
      whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.6 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="border-b border-line"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-6 py-6 text-left"
      >
        <span className="font-display text-lg uppercase leading-snug text-ink lg:text-xl">{q}</span>
        <ChevronDown
          size={20}
          className={cn(
            "shrink-0 text-steel-500 transition-transform duration-[--duration-standard]",
            open && "rotate-180",
          )}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={transition.standard}
            className="overflow-hidden"
          >
            <p className="max-w-2xl pb-6 text-sm leading-relaxed text-steel-400">{a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
