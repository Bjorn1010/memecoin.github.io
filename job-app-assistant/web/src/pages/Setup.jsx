import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useToast } from "../components/Toast.jsx";
import {
  IconUserCircle,
  IconFileText,
  IconGraduationCap,
  IconUpload,
  IconCheckCircle,
  IconLoader,
} from "../components/Icons.jsx";

function SectionHeader({ icon, title, subtitle }) {
  return (
    <div className="flex items-start gap-3 mb-4">
      <span className="grid place-items-center w-9 h-9 shrink-0 rounded-xl bg-indigo-50 text-indigo-600">
        {icon}
      </span>
      <div>
        <h2 className="font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function FileField({ label, accept, filename, onChange }) {
  return (
    <div>
      {label && <label className="label">{label}</label>}
      <label className="file-drop">
        <IconUpload className="w-5 h-5 text-slate-400 shrink-0" />
        <span className="flex-1">
          {filename ? "Remplacer le fichier" : "Choisir un fichier…"}
        </span>
        <input type="file" accept={accept} onChange={onChange} className="hidden" />
      </label>
      {filename && (
        <p className="flex items-center gap-1.5 text-sm text-emerald-700 mt-2">
          <IconCheckCircle className="w-4 h-4 shrink-0" />
          {filename}
        </p>
      )}
    </div>
  );
}

const BULLETIN_LABELS = {
  1: "Année 1 (la plus ancienne)",
  2: "Année 2",
  3: "Année 3 (la plus récente)",
};

export default function Setup() {
  const toast = useToast();
  const [profile, setProfile] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.getProfile().then(setProfile);
  useEffect(() => {
    load();
  }, []);

  if (!profile) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-8 w-40" />
        <div className="skeleton h-28" />
        <div className="skeleton h-28" />
      </div>
    );
  }

  const set = (key) => (e) => setProfile({ ...profile, [key]: e.target.value });

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateProfile(profile);
      setProfile(updated);
      toast.success("Profil enregistré.");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCvUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const updated = await api.uploadCv(file);
      setProfile({ ...profile, ...updated });
      toast.success("CV importé et texte extrait avec succès.");
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleCoverLetterUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const updated = await api.uploadCoverLetter(file);
      setProfile({ ...profile, ...updated });
      toast.success("Lettre de motivation importée et texte extrait avec succès.");
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleBulletinUpload = (n) => async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const updated = await api.uploadBulletin(n, file);
      setProfile({ ...profile, ...updated });
      toast.success("Bulletin importé avec succès.");
    } catch (err) {
      toast.error(err.message);
    }
  };

  const steps = [
    !!profile.full_name,
    profile.has_cv_docx,
    !!profile.cover_letter_text,
    profile.has_bulletin1,
    profile.has_bulletin2,
    profile.has_bulletin3,
  ];
  const doneCount = steps.filter(Boolean).length;
  const complete = doneCount === steps.length;

  return (
    <div className="space-y-6 pb-24">
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-900">Ton profil</h1>
        <p className="text-sm text-slate-500 mt-1">
          À remplir une seule fois — sert de base pour toutes tes candidatures.
        </p>
      </div>

      <div className="card card-pad">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-slate-700">
            {complete ? "Profil complet" : "Progression du profil"}
          </p>
          <p className="text-sm text-slate-500">{doneCount}/{steps.length}</p>
        </div>
        <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              complete ? "bg-emerald-500" : "bg-gradient-to-r from-indigo-500 to-violet-500"
            }`}
            style={{ width: `${(doneCount / steps.length) * 100}%` }}
          />
        </div>
      </div>

      <section className="card card-pad">
        <SectionHeader icon={<IconUserCircle className="w-5 h-5" />} title="Mes informations" />
        <label className="label">Prénom / nom complet</label>
        <input className="input" value={profile.full_name || ""} onChange={set("full_name")} />
      </section>

      <section className="card card-pad">
        <SectionHeader
          icon={<IconFileText className="w-5 h-5" />}
          title="CV"
          subtitle="Fichier Word (.docx), utilisé tel quel pour chaque candidature — il n'est modifié que très rarement, sur décision de l'IA."
        />
        <FileField accept=".docx" filename={profile.cv_filename} onChange={handleCvUpload} />
      </section>

      <section className="card card-pad">
        <SectionHeader
          icon={<IconFileText className="w-5 h-5" />}
          title="Lettre de motivation de référence"
          subtitle="Glisse un fichier Word, ou colle le texte ci-dessous. Sert de style et de base : l'IA l'adapte à 100% à chaque entreprise."
        />
        <FileField accept=".docx" onChange={handleCoverLetterUpload} />
        <textarea
          className="input mt-3"
          rows={8}
          placeholder="…ou colle ta lettre ici"
          value={profile.cover_letter_text || ""}
          onChange={set("cover_letter_text")}
        />
      </section>

      <section className="card card-pad">
        <SectionHeader
          icon={<IconGraduationCap className="w-5 h-5" />}
          title="Bulletins scolaires"
          subtitle="Un fichier par année (PDF, image ou Word) — joints au téléchargement pour chaque candidature, comme le CV et la lettre."
        />
        <div className="grid sm:grid-cols-3 gap-3">
          {[1, 2, 3].map((n) => (
            <FileField
              key={n}
              label={BULLETIN_LABELS[n]}
              filename={profile[`bulletin${n}_filename`]}
              onChange={handleBulletinUpload(n)}
            />
          ))}
        </div>
      </section>

      <div className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur border-t border-slate-200 px-4 py-3 sm:static sm:bg-transparent sm:backdrop-blur-none sm:border-0 sm:px-0 sm:py-0">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <button onClick={save} disabled={saving} className="btn-primary">
            {saving && <IconLoader className="w-4 h-4 animate-spin-slow" />}
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
