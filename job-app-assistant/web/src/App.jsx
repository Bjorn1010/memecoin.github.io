import { useEffect, useState } from "react";
import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import { api } from "./api.js";
import { IconBuilding, IconUserCircle, IconLogOut, IconSparkles } from "./components/Icons.jsx";
import Login from "./pages/Login.jsx";
import Setup from "./pages/Setup.jsx";
import Companies from "./pages/Companies.jsx";
import CompanyDetail from "./pages/CompanyDetail.jsx";

function NavBar({ onLogout }) {
  const linkClass = ({ isActive }) =>
    `flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive ? "bg-indigo-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100"
    }`;
  return (
    <nav className="bg-white/90 backdrop-blur border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 font-display font-bold text-slate-900">
          <span className="grid place-items-center w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm">
            <IconSparkles className="w-4 h-4" />
          </span>
          <span className="hidden xs:inline">Assistant Candidatures</span>
        </div>
        <div className="flex items-center gap-1 flex-wrap">
          <NavLink to="/entreprises" className={linkClass}>
            <IconBuilding className="w-4 h-4" />
            Entreprises
          </NavLink>
          <NavLink to="/profil" className={linkClass}>
            <IconUserCircle className="w-4 h-4" />
            Profil
          </NavLink>
          <button
            onClick={onLogout}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
          >
            <IconLogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Déconnexion</span>
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
    return (
      <div className="min-h-screen grid place-items-center text-slate-400 text-sm">
        Chargement…
      </div>
    );
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
      <main className="max-w-4xl mx-auto px-4 py-6 sm:py-8">
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
