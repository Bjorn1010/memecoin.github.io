import { Check, X } from "lucide-react";

/* Four cards, each staging the same contrast: what buying here gets you
 * against what buying from an unlicensed reseller gets you. The comparison
 * format does the persuading — a claim is easy to make, a claim next to the
 * alternative it is implicitly against is harder to wave off. */
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
  return (
    <ul className="grid gap-px border border-line bg-line sm:grid-cols-2">
      {ITEMS.map(({ good, bad }, i) => (
        <li key={i} className="flex flex-col gap-4 bg-base p-7 lg:p-9">
          <div className="flex items-start gap-3">
            <Check size={18} strokeWidth={2.5} className="mt-0.5 shrink-0 text-volt" />
            <p className="font-display text-base uppercase leading-snug text-ink">{good}</p>
          </div>
          <div className="flex items-start gap-3">
            <X size={18} strokeWidth={2.5} className="mt-0.5 shrink-0 text-steel-600" />
            <p className="text-sm leading-relaxed text-steel-500">{bad}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
