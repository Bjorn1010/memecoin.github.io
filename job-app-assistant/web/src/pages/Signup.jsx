import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { IconLoader } from "../components/Icons.jsx";

export default function Signup({ onSuccess }) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await api.signup(email, password, fullName);
      onSuccess(user);
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
        <Link to="/" className="flex flex-col items-center text-center mb-6">
          <img
            src="/logo.png"
            alt="CandidAI"
            className="w-14 h-14 rounded-2xl shadow-md shadow-indigo-950/50 mb-3"
          />
          <h1 className="font-display text-xl font-bold text-white">Créer un compte</h1>
          <p className="text-sm text-slate-400 mt-1">Gratuit, prêt en 30 secondes</p>
        </Link>

        <label className="label" htmlFor="full_name">
          Prénom / nom
        </label>
        <input
          id="full_name"
          autoFocus
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="input mb-4"
        />

        <label className="label" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="input mb-4"
        />

        <label className="label" htmlFor="password">
          Mot de passe
        </label>
        <input
          id="password"
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input mb-1"
        />
        <p className="text-xs text-slate-500 mb-4">Au moins 8 caractères.</p>

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
        <button type="submit" disabled={loading} className="btn-primary w-full">
          {loading && <IconLoader className="w-4 h-4 animate-spin-slow" />}
          {loading ? "Création…" : "Créer mon compte"}
        </button>

        <p className="text-sm text-slate-400 text-center mt-5">
          Déjà un compte ?{" "}
          <Link to="/connexion" className="text-indigo-400 hover:text-indigo-300 font-medium">
            Se connecter
          </Link>
        </p>
      </form>
    </div>
  );
}
