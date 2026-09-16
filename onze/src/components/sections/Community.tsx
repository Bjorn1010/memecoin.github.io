import { Star } from "lucide-react";

/* Customer reviews.
 *
 * There is no review data in this project, and inventing testimonials for a
 * storefront is the one piece of "content" that is actually a lie about other
 * people. So these are labelled placeholders: real structure, real layout,
 * and a notice saying exactly what they are. Wire a review source in and
 * delete the notice — the markup does not change. */

const PLACEHOLDERS = [
  { name: "Prénom N.", product: "Maillot domicile", body: "Emplacement réservé à un avis client vérifié." },
  { name: "Prénom N.", product: "Maillot extérieur", body: "Emplacement réservé à un avis client vérifié." },
  { name: "Prénom N.", product: "Maillot rétro", body: "Emplacement réservé à un avis client vérifié." },
];

export function Community() {
  return (
    <div>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow label-mono mb-5">La communauté</p>
          <h2 className="font-display text-title text-ink">Ce qu&apos;ils en disent</h2>
        </div>
        <p className="max-w-sm text-xs leading-relaxed text-steel-500">
          Aucun avis n&apos;est encore collecté sur cette boutique. Les blocs ci-dessous sont des
          emplacements, pas des témoignages : ils seront remplacés par les avis réels dès qu&apos;une
          source sera connectée.
        </p>
      </div>

      <ul className="grid gap-3 md:grid-cols-3">
        {PLACEHOLDERS.map((review, i) => (
          <li key={i} className="border border-dashed border-steel-600 bg-base p-6">
            <div className="flex gap-0.5 text-steel-500" aria-hidden>
              {Array.from({ length: 5 }).map((_, s) => (
                <Star key={s} size={14} strokeWidth={1.5} />
              ))}
            </div>
            <p className="mt-4 text-sm leading-relaxed text-steel-400">{review.body}</p>
            <p className="label-mono mt-5 text-steel-500">
              {review.name} · {review.product}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
