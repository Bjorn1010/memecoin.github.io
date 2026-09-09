import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";

const inputClass = "w-full border border-slate-300 rounded-md px-3 py-2";

export default function CompanyDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [company, setCompany] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = () => api.getCompany(id).then(setCompany);
  useEffect(() => {
    load();
  }, [id]);

  if (!company) return <p className="text-slate-500">Chargement…</p>;

  const cvSuggestions = (() => {
    try {
      return JSON.parse(company.cv_suggestions || "[]");
    } catch {
      return [];
    }
  })();

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
        contact_email: company.contact_email,
        cover_letter_text: company.cover_letter_text,
        email_subject: company.email_subject,
        email_body: company.email_body,
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
      setMessage("Lettre de motivation et email générés.");
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const send = async () => {
    if (!confirm(`Envoyer la candidature à ${company.contact_email} ?`)) return;
    setSending(true);
    setError("");
    setMessage("");
    try {
      await save();
      const updated = await api.sendOne(id);
      setCompany(updated);
      setMessage("Candidature envoyée !");
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  };

  const removeCompany = async () => {
    if (!confirm("Supprimer cette entreprise ?")) return;
    await api.deleteCompany(id);
    navigate("/entreprises");
  };

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
            <label className="block text-sm text-slate-600 mb-1">Email de contact</label>
            <input className={inputClass} value={company.contact_email} onChange={set("contact_email")} />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Lien</label>
            <input className={inputClass} value={company.url} onChange={set("url")} />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Où trouvée</label>
            <input className={inputClass} value={company.source} onChange={set("source")} />
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
          {generating ? "Génération en cours…" : "Générer la candidature (IA)"}
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

      {(company.cover_letter_text || company.email_body) && (
        <>
          <section className="bg-white border border-slate-200 rounded-xl p-5">
            <h2 className="font-semibold text-slate-800 mb-2">Lettre de motivation générée</h2>
            <textarea
              className={inputClass}
              rows={14}
              value={company.cover_letter_text || ""}
              onChange={set("cover_letter_text")}
            />
          </section>

          {cvSuggestions.length > 0 && (
            <section className="bg-amber-50 border border-amber-200 rounded-xl p-5">
              <h2 className="font-semibold text-amber-800 mb-2">
                Suggestions de modification du CV (à toi de décider — le CV n'est pas modifié automatiquement)
              </h2>
              <ul className="list-disc list-inside text-sm text-amber-900 space-y-1">
                {cvSuggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </section>
          )}

          <section className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
            <h2 className="font-semibold text-slate-800">Email de candidature</h2>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Objet</label>
              <input className={inputClass} value={company.email_subject || ""} onChange={set("email_subject")} />
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Corps du message</label>
              <textarea
                className={inputClass}
                rows={8}
                value={company.email_body || ""}
                onChange={set("email_body")}
              />
            </div>
            <p className="text-xs text-slate-500">
              Le CV et la lettre de motivation (au format .docx) seront joints automatiquement.
            </p>
            <button
              onClick={send}
              disabled={sending || company.status === "sent"}
              className="bg-emerald-600 text-white rounded-md px-4 py-2 font-medium hover:bg-emerald-700 disabled:opacity-50"
            >
              {company.status === "sent"
                ? `Envoyée le ${new Date(company.sent_at).toLocaleString("fr-FR")}`
                : sending
                ? "Envoi…"
                : "Envoyer l'email"}
            </button>
          </section>
        </>
      )}
    </div>
  );
}
