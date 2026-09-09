import { useEffect, useState } from "react";
import { api } from "../api.js";

function Field({ label, children }) {
  return (
    <div className="mb-3">
      <label className="block text-sm text-slate-600 mb-1">{label}</label>
      {children}
    </div>
  );
}

const inputClass =
  "w-full border border-slate-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400";

export default function Setup() {
  const [profile, setProfile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = () => api.getProfile().then(setProfile);
  useEffect(() => {
    load();
  }, []);

  if (!profile) return <p className="text-slate-500">Chargement…</p>;

  const set = (key) => (e) =>
    setProfile({ ...profile, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const save = async () => {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const updated = await api.updateProfile(profile);
      setProfile({ ...updated, smtp_pass: "" });
      setMessage("Profil enregistré.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCvUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      const updated = await api.uploadCv(file);
      setProfile({ ...profile, ...updated, smtp_pass: "" });
      setMessage("CV importé et texte extrait avec succès.");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-8">
      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="font-semibold text-slate-800 mb-3">Mes informations</h2>
        <Field label="Nom complet">
          <input className={inputClass} value={profile.full_name || ""} onChange={set("full_name")} />
        </Field>
      </section>

      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="font-semibold text-slate-800 mb-1">CV</h2>
        <p className="text-sm text-slate-500 mb-3">
          Fichier Word (.docx). Il sera joint tel quel à chaque candidature — il n'est modifié
          que très rarement, sur ta décision, à partir des suggestions données par entreprise.
        </p>
        <input type="file" accept=".docx" onChange={handleCvUpload} className="mb-2" />
        {profile.cv_filename && (
          <p className="text-sm text-slate-600">Fichier actuel : {profile.cv_filename}</p>
        )}
      </section>

      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="font-semibold text-slate-800 mb-1">Lettre de motivation de référence</h2>
        <p className="text-sm text-slate-500 mb-3">
          Colle ici ta lettre de motivation "de base" (texte). Elle sert de style et de contenu de
          départ : l'IA l'adapte à 100% à chaque entreprise, et l'améliore si besoin.
        </p>
        <textarea
          className={inputClass}
          rows={10}
          value={profile.cover_letter_text || ""}
          onChange={set("cover_letter_text")}
        />
      </section>

      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="font-semibold text-slate-800 mb-1">Envoi d'email (SMTP)</h2>
        <p className="text-sm text-slate-500 mb-3">
          Pour Gmail : hôte smtp.gmail.com, port 587, et un "mot de passe d'application" (pas ton
          mot de passe normal) — à créer sur myaccount.google.com/apppasswords.
        </p>
        <div className="grid sm:grid-cols-2 gap-x-4">
          <Field label="Hôte SMTP">
            <input className={inputClass} value={profile.smtp_host || ""} onChange={set("smtp_host")} />
          </Field>
          <Field label="Port">
            <input
              type="number"
              className={inputClass}
              value={profile.smtp_port || 587}
              onChange={set("smtp_port")}
            />
          </Field>
          <Field label="Adresse email d'envoi (utilisateur)">
            <input className={inputClass} value={profile.smtp_user || ""} onChange={set("smtp_user")} />
          </Field>
          <Field label={`Mot de passe${profile.smtp_pass_set ? " (déjà défini, laisser vide pour garder)" : ""}`}>
            <input
              type="password"
              className={inputClass}
              value={profile.smtp_pass || ""}
              onChange={set("smtp_pass")}
            />
          </Field>
          <Field label="Nom affiché comme expéditeur">
            <input className={inputClass} value={profile.smtp_from_name || ""} onChange={set("smtp_from_name")} />
          </Field>
          <Field label="Email affiché comme expéditeur (souvent identique à l'utilisateur)">
            <input className={inputClass} value={profile.smtp_from_email || ""} onChange={set("smtp_from_email")} />
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600 mt-1">
          <input type="checkbox" checked={!!profile.smtp_secure} onChange={set("smtp_secure")} />
          Connexion sécurisée directe (SSL, généralement port 465 uniquement)
        </label>
      </section>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {message && <p className="text-emerald-600 text-sm">{message}</p>}

      <button
        onClick={save}
        disabled={saving}
        className="bg-indigo-600 text-white rounded-md px-4 py-2 font-medium hover:bg-indigo-700 disabled:opacity-50"
      >
        {saving ? "Enregistrement…" : "Enregistrer"}
      </button>
    </div>
  );
}
