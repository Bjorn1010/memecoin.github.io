"use client";

import { motion, useReducedMotion } from "motion/react";
import { Check, X } from "lucide-react";

/* Four cards, each staging the same contrast: what buying here gets you
 * against what buying from an unlicensed reseller gets you. The comparison
 * format does the persuading — a claim is easy to make, a claim next to the
 * alternative it is implicitly against is harder to wave off.
 *
 * Staggered into view rather than rendered flat: the rest of the page stages
 * its grids the same way, and four cards landing one after another reads as
 * a sequence of points being made, not a wall of text arriving at once. */
const ITEMS = [
  {
    good: "Maillots sous licence officielle des clubs et fédérations.",
    bad: "Répliques non-licenciées, flocage approximatif.",
  },
  {
    good: "Flocage nom et numéro inclus, sans supplément.",
    bad: "Personnalisation facturée à part, souvent au poids de lettre.",
  },
  {
    good: "Expédié sous 48 h depuis la Suisse, suivi fourni.",
    bad: "Trois à six semaines depuis l'étranger, sans suivi.",
  },
  {
    good: "Retours acceptés 30 jours, remboursement garanti.",
    bad: "Aucune politique de retour, litige sans recours.",
  },
];

export function WhyOnze() {
  const reduced = useReducedMotion();

  return (
    <ul className="grid gap-px border border-line bg-line sm:grid-cols-2">
      {ITEMS.map(({ good, bad }, i) => (
        <motion.li
          key={i}
          initial={reduced ? undefined : { opacity: 0, y: 24 }}
          whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col gap-4 bg-base p-7 lg:p-9"
        >
          <div className="flex items-start gap-3">
            <Check size={18} strokeWidth={2.5} className="mt-0.5 shrink-0 text-volt" />
            <p className="font-display text-base uppercase leading-snug text-ink">{good}</p>
          </div>
          <div className="flex items-start gap-3">
            <X size={18} strokeWidth={2.5} className="mt-0.5 shrink-0 text-steel-600" />
            <p className="text-sm leading-relaxed text-steel-500">{bad}</p>
          </div>
        </motion.li>
      ))}
    </ul>
  );
}
