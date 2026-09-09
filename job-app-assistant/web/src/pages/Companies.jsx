import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

const statusLabel = {
  pending: "En attente",
  generated: "Lettre générée",
  sent: "Envoyée",
};
const statusClass = {
  pending: "bg-slate-100 text-slate-600",
  generated: "bg-amber-100 text-amber-700",
  sent: "bg-emerald-100 text-emerald-700",
};

export default function Companies() {
  const [companies, setCompanies] = useState([]);
  const [form, setForm] = useState({ name: "", url: "", description: "", source: "", contact_email: "" });
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [bulkMessage, setBulkMessage] = useState("");
  const [error, setError] = useState("");

  const load = () => api.listCompanies().then(setCompanies);
  useEffect(() => {
    load();
  }, []);

  const addCompany = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.addCompany(form);
      setForm({ name: "", url: "", description: "", source: "", contact_email: "" });
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const removeCompany = async (id) => {
    if (!confirm("Supprimer cette entreprise ?")) return;
    await api.deleteCompany(id);
    load();
  };

  const generateAll = async () => {
    setBusy(true);
    setBulkMessage("");
    try {
      const res = await api.generateAll();
      setBulkMessage(`${res.processed} lettre(s) générée(s).`);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const sendAll = async () => {
    if (!confirm("Envoyer les candidatures prêtes (lettre générée + email de contact renseigné) ?")) return;
    setBusy(true);
    setBulkMessage("");
    try {
      const res = await api.sendAll();
      const ok = res.results.filter((r) => r.ok).length;
      setBulkMessage(`${ok}/${res.processed} email(s) envoyé(s).`);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const pendingCount = companies.filter((c) => c.status === "pending").length;
  const readyCount = companies.filter((c) => c.status === "generated" && c.contact_email).length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2 justify-between items-center">
        <h1 className="text-xl font-semibold text-slate-800">Entreprises</h1>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setShowForm((v) => !v)}
            className="bg-indigo-600 text-white rounded-md px-3 py-2 text-sm font-medium hover:bg-indigo-700"
          >
            + Ajouter une entreprise
          </button>
          <button
            onClick={generateAll}
            disabled={busy || pendingCount === 0}
            className="bg-white border border-slate-300 rounded-md px-3 py-2 text-sm font-medium hover:bg-slate-100 disabled:opacity-50"
          >
            Générer tout ({pendingCount} en attente)
          </button>
          <button
            onClick={sendAll}
            disabled={busy || readyCount === 0}
            className="bg-emerald-600 text-white rounded-md px-3 py-2 text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            Envoyer tout ({readyCount} prêtes)
          </button>
        </div>
      </div>

      {bulkMessage && <p className="text-emerald-600 text-sm">{bulkMessage}</p>}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      {showForm && (
        <form onSubmit={addCompany} className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
          <div>
            <label className="block text-sm text-slate-600 mb-1">Nom de l'entreprise *</label>
            <input
              required
              className="w-full border border-slate-300 rounded-md px-3 py-2"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">
              Lien (offre d'emploi, site carrière…)
            </label>
            <input
              className="w-full border border-slate-300 rounded-md px-3 py-2"
              placeholder="https://…"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">
              Description (si pas de lien, ou infos en plus)
            </label>
            <textarea
              className="w-full border border-slate-300 rounded-md px-3 py-2"
              rows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">
              Où as-tu trouvé cette offre/entreprise ?
            </label>
            <input
              className="w-full border border-slate-300 rounded-md px-3 py-2"
              placeholder="Ex : offre LinkedIn, site carrière, salon, recommandation…"
              value={form.source}
              onChange={(e) => setForm({ ...form, source: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Email de contact (pour l'envoi)</label>
            <input
              type="email"
              className="w-full border border-slate-300 rounded-md px-3 py-2"
              value={form.contact_email}
              onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
            />
          </div>
          <button className="bg-indigo-600 text-white rounded-md px-4 py-2 font-medium hover:bg-indigo-700">
            Ajouter
          </button>
        </form>
      )}

      <div className="space-y-2">
        {companies.length === 0 && (
          <p className="text-slate-500 text-sm">Aucune entreprise pour l'instant. Ajoutes-en une !</p>
        )}
        {companies.map((c) => (
          <div
            key={c.id}
            className="bg-white border border-slate-200 rounded-xl p-4 flex items-center justify-between gap-3 flex-wrap"
          >
            <div>
              <Link to={`/entreprises/${c.id}`} className="font-medium text-indigo-700 hover:underline">
                {c.name}
              </Link>
              <div className="text-xs text-slate-500">{c.source || c.url || "—"}</div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusClass[c.status]}`}>
                {statusLabel[c.status] || c.status}
              </span>
              <button
                onClick={() => removeCompany(c.id)}
                className="text-slate-400 hover:text-red-600 text-sm"
                title="Supprimer"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
