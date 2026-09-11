import { Link } from "react-router-dom";
import {
  IconSparkles,
  IconFileText,
  IconGraduationCap,
  IconDownload,
  IconCheckCircle,
} from "../components/Icons.jsx";

function NavBar() {
  return (
    <header className="relative z-10 max-w-5xl mx-auto px-4 py-5 flex items-center justify-between">
      <div className="flex items-center gap-2 font-display font-bold text-white">
        <img src="/logo.png" alt="CandidAI" className="w-8 h-8 rounded-lg" />
        CandidAI
      </div>
      <nav className="flex items-center gap-2 sm:gap-4">
        <Link
          to="/tarifs"
          className="px-3 py-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
        >
          Tarifs
        </Link>
        <Link
          to="/connexion"
          className="px-3 py-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
        >
          Se connecter
        </Link>
        <Link to="/inscription" className="btn-primary !py-2">
          Créer un compte
        </Link>
      </nav>
    </header>
  );
}

const features = [
  {
    icon: IconSparkles,
    title: "Lettre adaptée à 100%",
    text: "L'IA réécrit ta lettre de motivation pour chaque entreprise à partir de ta lettre de référence — et l'améliore si besoin.",
  },
  {
    icon: IconFileText,
    title: "CV modifié quand ça compte",
    text: "Rarement, mais quand une entreprise le justifie vraiment, l'IA te propose un CV réordonné — jamais de contenu inventé.",
  },
  {
    icon: IconGraduationCap,
    title: "Tous tes documents au même endroit",
    text: "CV, lettre, bulletins scolaires : uploade-les une fois, ils sont prêts pour chaque candidature.",
  },
  {
    icon: IconDownload,
    title: "Des fichiers, pas du bricolage",
    text: "Télécharge tout en un clic avec un message d'accompagnement déjà rédigé, et envoie-le toi-même.",
  },
];

const steps = [
  "Renseigne ton CV, ta lettre de référence et tes bulletins une seule fois.",
  "Ajoute une entreprise (nom, lien de l'offre, où tu l'as trouvée).",
  "Génère, télécharge, envoie — recommence pour chaque candidature en quelques secondes.",
];

export default function Landing() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950">
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[40rem] h-[40rem] rounded-full bg-indigo-600/20 blur-3xl" />
      <div className="pointer-events-none absolute top-40 -right-40 w-96 h-96 rounded-full bg-violet-600/15 blur-3xl" />

      <NavBar />

      <main className="relative z-10 max-w-3xl mx-auto px-4 text-center pt-16 pb-20">
        <span className="badge bg-indigo-500/15 text-indigo-300 mb-5">
          <IconSparkles className="w-3.5 h-3.5" />
          Candidatures assistées par IA
        </span>
        <h1 className="font-display text-4xl sm:text-5xl font-extrabold text-white leading-tight">
          Postule plus vite,
          <br />
          sans sacrifier la qualité.
        </h1>
        <p className="text-slate-400 text-lg mt-5 max-w-xl mx-auto">
          CandidAI adapte ta lettre de motivation à chaque entreprise, prépare tous tes documents,
          et te laisse juste les envoyer.
        </p>
        <div className="flex flex-wrap justify-center gap-3 mt-8">
          <Link to="/inscription" className="btn-primary text-base px-6 py-3">
            Créer un compte gratuit
          </Link>
          <Link to="/tarifs" className="btn-secondary text-base px-6 py-3">
            Voir les tarifs
          </Link>
        </div>
      </main>

      <section className="relative z-10 max-w-5xl mx-auto px-4 pb-20">
        <div className="grid sm:grid-cols-2 gap-4">
          {features.map(({ icon: Icon, title, text }) => (
            <div key={title} className="card card-pad">
              <span className="grid place-items-center w-10 h-10 rounded-xl bg-indigo-500/15 text-indigo-400 mb-3">
                <Icon className="w-5 h-5" />
              </span>
              <h3 className="font-semibold text-white">{title}</h3>
              <p className="text-sm text-slate-400 mt-1.5">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="relative z-10 max-w-3xl mx-auto px-4 pb-24">
        <h2 className="font-display text-2xl font-bold text-white text-center mb-8">
          Comment ça marche
        </h2>
        <div className="space-y-4">
          {steps.map((text, i) => (
            <div key={i} className="card card-pad flex items-start gap-4">
              <span className="grid place-items-center w-8 h-8 shrink-0 rounded-full bg-indigo-500/15 text-indigo-400 font-display font-bold text-sm">
                {i + 1}
              </span>
              <p className="text-slate-200 pt-1">{text}</p>
            </div>
          ))}
        </div>
        <div className="text-center mt-10">
          <Link to="/inscription" className="btn-primary text-base px-6 py-3">
            <IconCheckCircle className="w-5 h-5" />
            Commencer gratuitement
          </Link>
        </div>
      </section>

      <footer className="relative z-10 border-t border-slate-800 py-8 text-center text-sm text-slate-500">
        CandidAI — {new Date().getFullYear()}
      </footer>
    </div>
  );
}
