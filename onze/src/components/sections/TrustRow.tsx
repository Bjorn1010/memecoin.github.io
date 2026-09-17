"use client";

import { motion, useReducedMotion } from "motion/react";
import { CreditCard, Headphones, RotateCcw, Truck } from "lucide-react";

/* Reassurance, kept to one quiet line. The brief's instinct is right: a shop
 * that shouts "SECURE PAYMENT!!" in a red box reads as a shop that expects to
 * be doubted. Four facts, small type, a hairline between them. */
const ITEMS = [
  { icon: Truck, title: "Expédition 48 h", body: "Départ de Suisse, suivi fourni." },
  { icon: CreditCard, title: "Paiement sécurisé", body: "Transaction chiffrée de bout en bout." },
  { icon: RotateCcw, title: "Retours 30 jours", body: "Article non porté, hors flocage sur mesure." },
  { icon: Headphones, title: "Support", body: "Une équipe qui connaît les tailles." },
];

export function TrustRow() {
  const reduced = useReducedMotion();
  return (
    <ul className="grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
      {ITEMS.map(({ icon: Icon, title, body }, i) => (
        <motion.li
          key={title}
          initial={reduced ? undefined : { opacity: 0, y: 20 }}
          whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.5, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
          className="flex gap-4 bg-base p-6"
        >
          <Icon size={20} strokeWidth={1.5} className="mt-0.5 shrink-0 text-volt" />
          <div>
            <p className="font-display text-base uppercase leading-none text-ink">{title}</p>
            <p className="mt-2 text-xs leading-relaxed text-steel-400">{body}</p>
          </div>
        </motion.li>
      ))}
    </ul>
  );
}
