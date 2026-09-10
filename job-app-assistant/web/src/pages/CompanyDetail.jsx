import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";

const inputClass = "w-full border border-slate-300 rounded-md px-3 py-2";

export default function CompanyDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [company, setCompany] = useState(null);
  const [profile, setProfile] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = () => {
    api.getCompany(id).then(setCompany);
    api.getProfile().then(setProfile);
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!company || !profile) return <p className="text-slate-500">Chargement…</p>;

  const set = (key) => (e) => setCompany({ ...company, [key]: e.target.value });

  const save = async () => {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const updated = await api.updateCompany(id, {
        name: company.name,
        url: company.url,
        description: company.description,
        source: company.source,
        message_text: company.message_text,
      });
      setCompany(updated);
      setMessage("Modifications enregistrées.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const generate = async () => {
    setGenerating(true);
    setError("");
    setMessage("");
    try {
      await save();
      const updated = await api.generateOne(id);
      setCompany(updated);
      setMessage("Documents générés — télécharge-les ci-dessous.");
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const markDone = async () => {
    try {
      const updated = await api.updateCompany(id, { status: "done" });
      setCompany(updated);
    } catch (err) {
      setError(err.message);
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
    <div className="space-y-5">
      <button onClick={() => navigate("/entreprises")} className="text-sm text-indigo-600 hover:underline">
        ← Retour
      </button>

      <section className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-slate-600 mb-1">Nom de l'entreprise</label>
            <input className={inputClass} value={company.name} onChange={set("name")} />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Où trouvée</label>
            <input className={inputClass} value={company.source} onChange={set("source")} />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-sm text-slate-600 mb-1">Lien</label>
            <input className={inputClass} value={company.url} onChange={set("url")} />
          </div>
        </div>
        <div>
          <label className="block text-sm text-slate-600 mb-1">Description</label>
          <textarea className={inputClass} rows={3} value={company.description} onChange={set("description")} />
        </div>
      </section>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={generate}
          disabled={generating}
          className="bg-indigo-600 text-white rounded-md px-4 py-2 font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {generating
            ? "Génération en cours…"
            : hasGenerated
            ? "Régénérer la candidature (IA)"
            : "Générer la candidature (IA)"}
        </button>
        <button
          onClick={save}
          disabled={saving}
          className="bg-white border border-slate-300 rounded-md px-4 py-2 font-medium hover:bg-slate-100 disabled:opacity-50"
        >
          {saving ? "Enregistrement…" : "Enregistrer les modifications"}
        </button>
        <button onClick={removeCompany} className="text-sm text-red-600 hover:underline ml-auto">
          Supprimer l'entreprise
        </button>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {message && <p className="text-emerald-600 text-sm">{message}</p>}

      {hasGenerated && (
        <>
          <section className="bg-white border border-slate-200 rounded-xl p-5 space-y-2">
            <h2 className="font-semibold text-slate-800 mb-1">Documents à envoyer</h2>
            <p className="text-sm text-slate-500 mb-2">
              Télécharge tout et envoie-les toi-même (email, SMS, en main propre…) avec le message
              ci-dessous.
            </p>
            <ul className="space-y-1 text-sm">
              <li>
                <a href="/api/profile/cv" className="text-indigo-600 hover:underline">
                  📄 CV{profile.cv_filename ? ` (${profile.cv_filename})` : ""}
                </a>
              </li>
              {company.cv_modified_text && (
                <li>
                  <a
                    href={`/api/companies/${company.id}/cv-modifie.docx`}
                    className="text-indigo-600 hover:underline"
                  >
                    📄 CV modifié pour cette candidature
                  </a>
                  {company.cv_change_summary && (
                    <span className="text-slate-500"> — {company.cv_change_summary}</span>
                  )}
                </li>
              )}
              <li>
                <a
                  href={`/api/companies/${company.id}/cover-letter.docx`}
                  className="text-indigo-600 hover:underline"
                >
                  📄 Lettre de motivation ({company.name})
                </a>
              </li>
              {bulletins.map((n) => (
                <li key={n}>
                  <a href={`/api/profile/bulletin${n}`} className="text-indigo-600 hover:underline">
                    📄 Bulletin {n} ({profile[`bulletin${n}_filename`]})
                  </a>
                </li>
              ))}
              {bulletins.length === 0 && (
                <li className="text-slate-400">
                  Aucun bulletin importé — ajoute-les dans la page Profil.
                </li>
              )}
            </ul>
          </section>

          <section className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
            <h2 className="font-semibold text-slate-800">Petit message d'accompagnement</h2>
            <p className="text-sm text-slate-500">
              À copier-coller dans ton email/SMS en attachant les fichiers ci-dessus.
            </p>
            <textarea
              className={inputClass}
              rows={6}
              value={company.message_text || ""}
              onChange={set("message_text")}
            />
          </section>

          <button
            onClick={markDone}
            disabled={company.status === "done"}
            className="bg-emerald-600 text-white rounded-md px-4 py-2 font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            {company.status === "done" ? "Marqué comme envoyé ✓" : "Marquer comme envoyé"}
          </button>
        </>
      )}
    </div>
  );
}
