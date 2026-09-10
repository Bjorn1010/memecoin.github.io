import { useState } from "react";
import { api } from "../api.js";
import { IconSparkles, IconLoader } from "../components/Icons.jsx";

export default function Login({ onSuccess }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.login(password);
      onSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center px-4 bg-gradient-to-b from-indigo-50 via-slate-50 to-slate-50">
      <form onSubmit={handleSubmit} className="card card-pad w-full max-w-sm">
        <div className="flex flex-col items-center text-center mb-6">
          <span className="grid place-items-center w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-200 mb-3">
            <IconSparkles className="w-6 h-6" />
          </span>
          <h1 className="font-display text-xl font-bold text-slate-900">Assistant Candidatures</h1>
          <p className="text-sm text-slate-500 mt-1">Connecte-toi pour continuer</p>
        </div>

        <label className="label" htmlFor="password">
          Mot de passe
        </label>
        <input
          id="password"
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input mb-4"
        />
        {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
        <button type="submit" disabled={loading} className="btn-primary w-full">
          {loading && <IconLoader className="w-4 h-4 animate-spin-slow" />}
          {loading ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </div>
  );
}
