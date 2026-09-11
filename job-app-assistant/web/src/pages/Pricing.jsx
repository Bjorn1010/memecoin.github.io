import { Link } from "react-router-dom";
import { IconCheck, IconSparkles } from "../components/Icons.jsx";

const plans = [
  {
    name: "Gratuit",
    price: "0€",
    period: "/mois",
    description: "Pour tester CandidAI sur tes premières candidatures.",
    features: [
      "1 profil (CV, lettre, bulletins)",
      "5 candidatures générées / mois",
      "Lettre de motivation adaptée par IA",
      "Téléchargement CV + lettre + bulletins",
    ],
    cta: "Créer un compte gratuit",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "9€",
    period: "/mois",
    description: "Pour une recherche d'emploi active.",
    features: [
      "Candidatures illimitées",
      "CV modifié par IA quand c'est pertinent",
      "Génération en masse pour toutes tes entreprises",
      "Historique complet des candidatures",
      "Support par email prioritaire",
    ],
    cta: "Bientôt disponible",
    highlighted: true,
  },
  {
    name: "Équipe",
    price: "Sur devis",
    period: "",
    description: "Pour les écoles, associations et accompagnateurs à l'emploi.",
    features: [
      "Plusieurs comptes gérés",
      "Statistiques d'utilisation",
      "Accompagnement à la mise en place",
      "Support dédié",
    ],
    cta: "Nous contacter",
    highlighted: false,
  },
];

export default function Pricing() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950">
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[40rem] h-[40rem] rounded-full bg-indigo-600/15 blur-3xl" />

      <header className="relative z-10 max-w-5xl mx-auto px-4 py-5 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-display font-bold text-white">
          <img src="/logo.png" alt="CandidAI" className="w-8 h-8 rounded-lg" />
          CandidAI
        </Link>
        <Link to="/connexion" className="btn-secondary !py-2">
          Se connecter
        </Link>
      </header>

      <main className="relative z-10 max-w-5xl mx-auto px-4 pb-24">
        <div className="text-center pt-10 pb-10">
          <h1 className="font-display text-3xl sm:text-4xl font-extrabold text-white">
            Des tarifs simples
          </h1>
          <p className="text-slate-400 mt-3 max-w-lg mx-auto">
            CandidAI est aujourd'hui gratuit pour tout le monde. Voici à quoi ressembleront nos
            offres une fois le produit lancé.
          </p>
        </div>

        <div className="card border-amber-500/30 bg-amber-500/5 card-pad flex items-start gap-3 mb-10 max-w-2xl mx-auto">
          <IconSparkles className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <p className="text-sm text-amber-200">
            <span className="font-semibold">CandidAI est en phase de lancement.</span> Ces tarifs
            sont indicatifs et pas encore actifs — seule l'offre Gratuite est disponible pour le
            moment, sans engagement ni carte bancaire.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-5">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`card card-pad flex flex-col ${
                plan.highlighted ? "border-indigo-500/60 shadow-card" : ""
              }`}
            >
              {plan.highlighted && (
                <span className="badge bg-indigo-500/15 text-indigo-300 self-start mb-3">
                  Bientôt
                </span>
              )}
              <h2 className="font-display text-lg font-bold text-white">{plan.name}</h2>
              <p className="text-sm text-slate-400 mt-1 mb-4">{plan.description}</p>
              <p className="mb-5">
                <span className="text-3xl font-display font-extrabold text-white">
                  {plan.price}
                </span>
                <span className="text-slate-400">{plan.period}</span>
              </p>
              <ul className="space-y-2.5 flex-1 mb-6">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-slate-300">
                    <IconCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    {f}
                  </li>
                ))}
              </ul>
              {plan.name === "Gratuit" ? (
                <Link to="/inscription" className="btn-primary w-full">
                  {plan.cta}
                </Link>
              ) : (
                <button disabled className="btn-secondary w-full opacity-60 cursor-not-allowed">
                  {plan.cta}
                </button>
              )}
            </div>
          ))}
        </div>
      </main>

      <footer className="relative z-10 border-t border-slate-800 py-8 text-center text-sm text-slate-500">
        CandidAI — {new Date().getFullYear()}
      </footer>
    </div>
  );
}
