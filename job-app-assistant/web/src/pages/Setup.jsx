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

const BULLETIN_LABELS = {
  1: "Bulletin - année 1 (la plus ancienne)",
  2: "Bulletin - année 2",
  3: "Bulletin - année 3 (la plus récente)",
};

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

  const set = (key) => (e) => setProfile({ ...profile, [key]: e.target.value });

  const save = async () => {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const updated = await api.updateProfile(profile);
      setProfile(updated);
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
      setProfile({ ...profile, ...updated });
      setMessage("CV importé et texte extrait avec succès.");
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCoverLetterUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      const updated = await api.uploadCoverLetter(file);
      setProfile({ ...profile, ...updated });
      setMessage("Lettre de motivation importée et texte extrait avec succès.");
    } catch (err) {
      setError(err.message);
    }
  };

  const handleBulletinUpload = (n) => async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      const updated = await api.uploadBulletin(n, file);
      setProfile({ ...profile, ...updated });
      setMessage("Bulletin importé avec succès.");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-8">
      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="font-semibold text-slate-800 mb-3">Mes informations</h2>
        <Field label="Prénom / nom complet">
          <input className={inputClass} value={profile.full_name || ""} onChange={set("full_name")} />
        </Field>
      </section>

      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="font-semibold text-slate-800 mb-1">CV</h2>
        <p className="text-sm text-slate-500 mb-3">
          Fichier Word (.docx). Il est utilisé tel quel pour chaque candidature — il n'est modifié
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
          Glisse un fichier Word (.docx) — comme pour le CV — ou colle directement le texte
          ci-dessous. Elle sert de style et de contenu de départ : l'IA l'adapte à 100% à chaque
          entreprise, et l'améliore si besoin.
        </p>
        <input type="file" accept=".docx" onChange={handleCoverLetterUpload} className="mb-3" />
        <textarea
          className={inputClass}
          rows={10}
          value={profile.cover_letter_text || ""}
          onChange={set("cover_letter_text")}
        />
      </section>

      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="font-semibold text-slate-800 mb-1">Bulletins scolaires (3 dernières années)</h2>
        <p className="text-sm text-slate-500 mb-3">
          PDF, image ou Word — un fichier par année. Ils seront proposés au téléchargement pour
          chaque candidature, comme le CV et la lettre.
        </p>
        <div className="space-y-3">
          {[1, 2, 3].map((n) => (
            <div key={n}>
              <label className="block text-sm text-slate-600 mb-1">{BULLETIN_LABELS[n]}</label>
              <input type="file" onChange={handleBulletinUpload(n)} className="mb-1" />
              {profile[`bulletin${n}_filename`] && (
                <p className="text-sm text-slate-600">
                  Fichier actuel : {profile[`bulletin${n}_filename`]}
                </p>
              )}
            </div>
          ))}
        </div>
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
