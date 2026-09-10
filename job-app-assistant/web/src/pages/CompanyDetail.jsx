import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useToast } from "../components/Toast.jsx";
import {
  IconArrowLeft,
  IconBuilding,
  IconSparkles,
  IconTrash,
  IconLoader,
  IconFileText,
  IconDownload,
  IconCheckCircle,
  IconGraduationCap,
} from "../components/Icons.jsx";

const statusLabel = { pending: "En attente", generated: "Prête", done: "Envoyée" };
const statusClass = {
  pending: "bg-slate-100 text-slate-600",
  generated: "bg-amber-100 text-amber-700",
  done: "bg-emerald-100 text-emerald-700",
};

function DocCard({ href, title, subtitle, icon }) {
  return (
    <a
      href={href}
      className="flex items-center gap-3 rounded-xl border border-slate-200 p-3.5 hover:border-indigo-300 hover:bg-indigo-50/40 transition-colors group"
    >
      <span className="grid place-items-center w-10 h-10 shrink-0 rounded-lg bg-indigo-50 text-indigo-600 group-hover:bg-indigo-100">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-slate-900 text-sm truncate">{title}</p>
        {subtitle && <p className="text-xs text-slate-500 truncate">{subtitle}</p>}
      </div>
      <IconDownload className="w-4 h-4 text-slate-400 shrink-0 group-hover:text-indigo-600" />
    </a>
  );
}

export default function CompanyDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [company, setCompany] = useState(null);
  const [profile, setProfile] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = () => {
    api.getCompany(id).then(setCompany);
    api.getProfile().then(setProfile);
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!company || !profile) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-5 w-24" />
        <div className="skeleton h-40" />
        <div className="skeleton h-24" />
      </div>
    );
  }

  const set = (key) => (e) => setCompany({ ...company, [key]: e.target.value });

  const save = async (silent) => {
    setSaving(true);
    try {
      const updated = await api.updateCompany(id, {
        name: company.name,
        url: company.url,
        description: company.description,
        source: company.source,
        message_text: company.message_text,
      });
      setCompany(updated);
      if (!silent) toast.success("Modifications enregistrées.");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const generate = async () => {
    setGenerating(true);
    try {
      await save(true);
      const updated = await api.generateOne(id);
      setCompany(updated);
      toast.success("Documents générés — télécharge-les ci-dessous.");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const markDone = async () => {
    try {
      const updated = await api.updateCompany(id, { status: "done" });
      setCompany(updated);
      toast.success("Marqué comme envoyé.");
    } catch (err) {
      toast.error(err.message);
    }
  };

  const removeCompany = async () => {
    if (!confirm("Supprimer cette entreprise ?")) return;
    await api.deleteCompany(id);
    navigate("/entreprises");
  };

  const bulletins = [1, 2, 3].filter((n) => profile[`has_bulletin${n}`]);
  const hasGenerated = company.cover_letter_text || company.message_text;

  return (
    <div className="space-y-6">
      <button
        onClick={() => navigate("/entreprises")}
        className="flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
      >
        <IconArrowLeft className="w-4 h-4" />
        Entreprises
      </button>

      <section className="card card-pad space-y-4">
        <div className="flex items-center gap-3">
          <span className="grid place-items-center w-10 h-10 shrink-0 rounded-xl bg-indigo-50 text-indigo-600">
            <IconBuilding className="w-5 h-5" />
          </span>
          <input
            className="font-display text-lg font-bold text-slate-900 bg-transparent border-0 focus:outline-none focus:ring-0 p-0 flex-1 min-w-0"
            value={company.name}
            onChange={set("name")}
          />
          <span className={`badge shrink-0 ${statusClass[company.status]}`}>
            {statusLabel[company.status] || company.status}
          </span>
        </div>
        <div className="grid sm:grid-cols-2 gap-3.5">
          <div>
            <label className="label">Où trouvée</label>
            <input className="input" value={company.source} onChange={set("source")} />
          </div>
          <div>
            <label className="label">Lien</label>
            <input className="input" value={company.url} onChange={set("url")} />
          </div>
        </div>
        <div>
          <label className="label">Description</label>
          <textarea className="input" rows={3} value={company.description} onChange={set("description")} />
        </div>
      </section>

      <div className="flex flex-wrap gap-2 items-center">
        <button onClick={generate} disabled={generating} className="btn-primary">
          {generating ? (
            <IconLoader className="w-4 h-4 animate-spin-slow" />
          ) : (
            <IconSparkles className="w-4 h-4" />
          )}
          {generating
            ? "Génération en cours…"
            : hasGenerated
            ? "Régénérer (IA)"
            : "Générer la candidature (IA)"}
        </button>
        <button onClick={() => save(false)} disabled={saving} className="btn-secondary">
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>
        <button onClick={removeCompany} className="btn-ghost-danger ml-auto">
          <IconTrash className="w-4 h-4" />
          Supprimer
        </button>
      </div>

      {hasGenerated && (
        <>
          <section className="card card-pad space-y-3 animate-fade-in">
            <div>
              <h2 className="font-semibold text-slate-900">Documents à envoyer</h2>
              <p className="text-sm text-slate-500 mt-0.5">
                Télécharge et envoie-les toi-même (email, SMS, en main propre…) avec le message
                ci-dessous.
              </p>
            </div>
            <div className="grid sm:grid-cols-2 gap-2.5">
              <DocCard
                href="/api/profile/cv"
                title="CV"
                subtitle={profile.cv_filename}
                icon={<IconFileText className="w-5 h-5" />}
              />
              {company.cv_modified_text && (
                <DocCard
                  href={`/api/companies/${company.id}/cv-modifie.docx`}
                  title="CV modifié pour cette candidature"
                  subtitle={company.cv_change_summary}
                  icon={<IconFileText className="w-5 h-5" />}
                />
              )}
              <DocCard
                href={`/api/companies/${company.id}/cover-letter.docx`}
                title="Lettre de motivation"
                subtitle={company.name}
                icon={<IconFileText className="w-5 h-5" />}
              />
              {bulletins.map((n) => (
                <DocCard
                  key={n}
                  href={`/api/profile/bulletin${n}`}
                  title={`Bulletin ${n}`}
                  subtitle={profile[`bulletin${n}_filename`]}
                  icon={<IconGraduationCap className="w-5 h-5" />}
                />
              ))}
            </div>
            {bulletins.length === 0 && (
              <p className="text-sm text-slate-400">
                Aucun bulletin importé — ajoute-les dans la page Profil.
              </p>
            )}
          </section>

          <section className="card card-pad space-y-3 animate-fade-in">
            <div>
              <h2 className="font-semibold text-slate-900">Petit message d'accompagnement</h2>
              <p className="text-sm text-slate-500 mt-0.5">
                À copier-coller dans ton email/SMS en attachant les fichiers ci-dessus.
              </p>
            </div>
            <textarea
              className="input"
              rows={6}
              value={company.message_text || ""}
              onChange={set("message_text")}
            />
          </section>

          <button onClick={markDone} disabled={company.status === "done"} className="btn-success">
            <IconCheckCircle className="w-4 h-4" />
            {company.status === "done" ? "Marqué comme envoyé" : "Marquer comme envoyé"}
          </button>
        </>
      )}
    </div>
  );
}
