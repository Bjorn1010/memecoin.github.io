import { useEffect, useState } from "react";
import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import { api } from "./api.js";
import Login from "./pages/Login.jsx";
import Setup from "./pages/Setup.jsx";
import Companies from "./pages/Companies.jsx";
import CompanyDetail from "./pages/CompanyDetail.jsx";

function NavBar({ onLogout }) {
  const linkClass = ({ isActive }) =>
    `px-3 py-2 rounded-md text-sm font-medium ${
      isActive ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-200"
    }`;
  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-4xl mx-auto px-4 py-2 flex items-center justify-between gap-2 flex-wrap">
        <span className="font-semibold text-indigo-700">Assistant Candidatures</span>
        <div className="flex gap-1 flex-wrap">
          <NavLink to="/entreprises" className={linkClass}>
            Entreprises
          </NavLink>
          <NavLink to="/profil" className={linkClass}>
            Profil
          </NavLink>
          <button
            onClick={onLogout}
            className="px-3 py-2 rounded-md text-sm font-medium text-slate-600 hover:bg-slate-200"
          >
            Déconnexion
          </button>
        </div>
      </div>
    </nav>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(null);

  useEffect(() => {
    api
      .me()
      .then((r) => setAuthed(r.authed))
      .catch(() => setAuthed(false));
  }, []);

  if (authed === null) {
    return <div className="p-8 text-center text-slate-500">Chargement…</div>;
  }

  if (!authed) {
    return <Login onSuccess={() => setAuthed(true)} />;
  }

  const handleLogout = async () => {
    await api.logout();
    setAuthed(false);
  };

  return (
    <div className="min-h-screen">
      <NavBar onLogout={handleLogout} />
      <main className="max-w-4xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/entreprises" replace />} />
          <Route path="/profil" element={<Setup />} />
          <Route path="/entreprises" element={<Companies />} />
          <Route path="/entreprises/:id" element={<CompanyDetail />} />
        </Routes>
      </main>
    </div>
  );
}
