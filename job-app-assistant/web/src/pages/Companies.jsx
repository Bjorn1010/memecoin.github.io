import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useToast } from "../components/Toast.jsx";
import {
  IconBuilding,
  IconPlus,
  IconSparkles,
  IconTrash,
  IconMapPin,
  IconLoader,
  IconCheckCircle,
  IconClock,
  IconInbox,
} from "../components/Icons.jsx";

const statusLabel = {
  pending: "En attente",
  generated: "Prête",
  done: "Envoyée",
};
const statusClass = {
  pending: "bg-slate-100 text-slate-600",
  generated: "bg-amber-100 text-amber-700",
  done: "bg-emerald-100 text-emerald-700",
};

function StatCard({ icon, label, value, tone }) {
  return (
    <div className="stat-card">
      <span className={`grid place-items-center w-10 h-10 shrink-0 rounded-xl ${tone}`}>{icon}</span>
      <div>
        <p className="text-2xl font-display font-bold text-slate-900 leading-none">{value}</p>
        <p className="text-xs text-slate-500 mt-1">{label}</p>
      </div>
    </div>
  );
}

export default function Companies() {
  const toast = useToast();
  const [companies, setCompanies] = useState(null);
  const [form, setForm] = useState({ name: "", url: "", description: "", source: "" });
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = () => api.listCompanies().then(setCompanies);
  useEffect(() => {
    load();
  }, []);

  const addCompany = async (e) => {
    e.preventDefault();
    try {
      await api.addCompany(form);
      setForm({ name: "", url: "", description: "", source: "" });
      setShowForm(false);
      load();
      toast.success("Entreprise ajoutée.");
    } catch (err) {
      toast.error(err.message);
    }
  };

  const removeCompany = async (id) => {
    if (!confirm("Supprimer cette entreprise ?")) return;
    await api.deleteCompany(id);
    load();
  };

  const generateAll = async () => {
    setBusy(true);
    try {
      const res = await api.generateAll();
      toast.success(`${res.processed} candidature(s) générée(s).`);
      load();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  const counts = {
    total: companies?.length || 0,
    pending: (companies || []).filter((c) => c.status === "pending").length,
    generated: (companies || []).filter((c) => c.status === "generated").length,
    done: (companies || []).filter((c) => c.status === "done").length,
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3 justify-between items-end">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">Entreprises</h1>
          <p className="text-sm text-slate-500 mt-1">Une fiche par candidature à préparer.</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => setShowForm((v) => !v)} className="btn-secondary">
            <IconPlus className="w-4 h-4" />
            Ajouter
          </button>
          <button
            onClick={generateAll}
            disabled={busy || counts.pending === 0}
            className="btn-primary"
          >
            {busy ? (
              <IconLoader className="w-4 h-4 animate-spin-slow" />
            ) : (
              <IconSparkles className="w-4 h-4" />
            )}
            Générer tout ({counts.pending})
          </button>
        </div>
      </div>

      {companies && companies.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard
            icon={<IconInbox className="w-5 h-5" />}
            label="Total"
            value={counts.total}
            tone="bg-slate-100 text-slate-600"
          />
          <StatCard
            icon={<IconClock className="w-5 h-5" />}
            label="En attente"
            value={counts.pending}
            tone="bg-slate-100 text-slate-600"
          />
          <StatCard
            icon={<IconSparkles className="w-5 h-5" />}
            label="Prêtes"
            value={counts.generated}
            tone="bg-amber-100 text-amber-700"
          />
          <StatCard
            icon={<IconCheckCircle className="w-5 h-5" />}
            label="Envoyées"
            value={counts.done}
            tone="bg-emerald-100 text-emerald-700"
          />
        </div>
      )}

      {showForm && (
        <form onSubmit={addCompany} className="card card-pad space-y-3.5 animate-fade-in">
          <div>
            <label className="label">Nom de l'entreprise *</label>
            <input
              required
              autoFocus
              className="input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Lien (offre d'emploi, site carrière…)</label>
            <input
              className="input"
              placeholder="https://…"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Description (si pas de lien, ou infos en plus)</label>
            <textarea
              className="input"
              rows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Où as-tu trouvé cette offre/entreprise ?</label>
            <input
              className="input"
              placeholder="Ex : offre LinkedIn, site carrière, salon, recommandation…"
              value={form.source}
              onChange={(e) => setForm({ ...form, source: e.target.value })}
            />
          </div>
          <button className="btn-primary">Ajouter</button>
        </form>
      )}

      <div className="space-y-2.5">
        {companies === null &&
          [0, 1, 2].map((i) => <div key={i} className="skeleton h-[72px]" />)}

        {companies && companies.length === 0 && (
          <div className="card card-pad text-center py-12">
            <span className="grid place-items-center w-12 h-12 mx-auto rounded-2xl bg-indigo-50 text-indigo-500 mb-3">
              <IconBuilding className="w-6 h-6" />
            </span>
            <p className="font-medium text-slate-700">Aucune entreprise pour l'instant</p>
            <p className="text-sm text-slate-500 mt-1">Ajoutes-en une pour commencer.</p>
          </div>
        )}

        {companies?.map((c) => (
          <div
            key={c.id}
            className="card card-pad flex items-center justify-between gap-3 flex-wrap hover:shadow-card transition-shadow"
          >
            <Link to={`/entreprises/${c.id}`} className="flex items-center gap-3 min-w-0 flex-1">
              <span className="grid place-items-center w-10 h-10 shrink-0 rounded-xl bg-indigo-50 text-indigo-600">
                <IconBuilding className="w-5 h-5" />
              </span>
              <div className="min-w-0">
                <p className="font-semibold text-slate-900 truncate">{c.name}</p>
                {(c.source || c.url) && (
                  <p className="flex items-center gap-1 text-xs text-slate-500 truncate mt-0.5">
                    <IconMapPin className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">{c.source || c.url}</span>
                  </p>
                )}
              </div>
            </Link>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`badge ${statusClass[c.status]}`}>
                {c.status === "done" && <IconCheckCircle className="w-3.5 h-3.5" />}
                {statusLabel[c.status] || c.status}
              </span>
              <button
                onClick={() => removeCompany(c.id)}
                className="p-2 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                title="Supprimer"
              >
                <IconTrash className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
