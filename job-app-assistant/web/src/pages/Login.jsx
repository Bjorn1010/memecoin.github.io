import { useState } from "react";
import { api } from "../api.js";
import { IconLoader } from "../components/Icons.jsx";

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
    <div className="relative min-h-screen grid place-items-center px-4 overflow-hidden bg-slate-950">
      <div className="pointer-events-none absolute -top-32 -left-24 w-96 h-96 rounded-full bg-indigo-600/25 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-32 -right-24 w-96 h-96 rounded-full bg-violet-600/25 blur-3xl" />

      <form
        onSubmit={handleSubmit}
        className="relative card card-pad w-full max-w-sm animate-fade-in"
      >
        <div className="flex flex-col items-center text-center mb-6">
          <img
            src="/logo.png"
            alt="CandidAI"
            className="w-14 h-14 rounded-2xl shadow-md shadow-indigo-950/50 mb-3"
          />
          <h1 className="font-display text-xl font-bold text-white">CandidAI</h1>
          <p className="text-sm text-slate-400 mt-1">Connecte-toi pour continuer</p>
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
        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
        <button type="submit" disabled={loading} className="btn-primary w-full">
          {loading && <IconLoader className="w-4 h-4 animate-spin-slow" />}
          {loading ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </div>
  );
}
