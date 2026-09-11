import { useEffect, useState } from "react";
import { Route, Routes, Navigate, useLocation } from "react-router-dom";
import { api } from "./api.js";
import { ToastProvider } from "./components/Toast.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { IconMenu } from "./components/Icons.jsx";
import Landing from "./pages/Landing.jsx";
import Pricing from "./pages/Pricing.jsx";
import Login from "./pages/Login.jsx";
import Signup from "./pages/Signup.jsx";
import Setup from "./pages/Setup.jsx";
import Companies from "./pages/Companies.jsx";
import CompanyDetail from "./pages/CompanyDetail.jsx";

function Shell({ onLogout }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen md:flex">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} onLogout={onLogout} />

      <div className="flex-1 min-w-0">
        <header className="md:hidden sticky top-0 z-20 bg-slate-950/90 backdrop-blur border-b border-slate-800 h-14 flex items-center gap-3 px-4">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 -ml-1.5 rounded-lg text-slate-400 hover:bg-slate-800"
          >
            <IconMenu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2 font-display font-bold text-white">
            <img src="/logo.png" alt="CandidAI" className="w-6 h-6 rounded-md" />
            CandidAI
          </div>
        </header>

        <main className="max-w-3xl mx-auto px-4 py-6 sm:py-10 animate-fade-in">
          <Routes>
            <Route path="/profil" element={<Setup />} />
            <Route path="/entreprises" element={<Companies />} />
            <Route path="/entreprises/:id" element={<CompanyDetail />} />
            <Route path="*" element={<Navigate to="/entreprises" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(null);

  useEffect(() => {
    api
      .me()
      .then((r) => setAuthed(!!r.authed))
      .catch(() => setAuthed(false));
  }, []);

  if (authed === null) {
    return (
      <div className="min-h-screen grid place-items-center bg-slate-950 text-slate-400 text-sm">
        Chargement…
      </div>
    );
  }

  const handleAuthed = () => setAuthed(true);
  const handleLogout = async () => {
    await api.logout();
    setAuthed(false);
  };

  return (
    <ToastProvider>
      <Routes>
        <Route path="/" element={authed ? <Navigate to="/entreprises" replace /> : <Landing />} />
        <Route path="/tarifs" element={<Pricing />} />
        <Route
          path="/connexion"
          element={authed ? <Navigate to="/entreprises" replace /> : <Login onSuccess={handleAuthed} />}
        />
        <Route
          path="/inscription"
          element={authed ? <Navigate to="/entreprises" replace /> : <Signup onSuccess={handleAuthed} />}
        />
        <Route
          path="/*"
          element={authed ? <Shell onLogout={handleLogout} /> : <Navigate to="/connexion" replace />}
        />
      </Routes>
    </ToastProvider>
  );
}
