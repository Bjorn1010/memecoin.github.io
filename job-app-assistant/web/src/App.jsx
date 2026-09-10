import { useEffect, useState } from "react";
import { Route, Routes, Navigate, useLocation } from "react-router-dom";
import { api } from "./api.js";
import { ToastProvider } from "./components/Toast.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { IconMenu, IconSparkles } from "./components/Icons.jsx";
import Login from "./pages/Login.jsx";
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
        <header className="md:hidden sticky top-0 z-20 bg-white/90 backdrop-blur border-b border-slate-200 h-14 flex items-center gap-3 px-4">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 -ml-1.5 rounded-lg text-slate-500 hover:bg-slate-100"
          >
            <IconMenu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2 font-display font-bold text-slate-900">
            <span className="grid place-items-center w-6 h-6 rounded-md bg-gradient-to-br from-indigo-600 to-violet-600 text-white">
              <IconSparkles className="w-3.5 h-3.5" />
            </span>
            Assistant Candidatures
          </div>
        </header>

        <main className="max-w-3xl mx-auto px-4 py-6 sm:py-10 animate-fade-in">
          <Routes>
            <Route path="/" element={<Navigate to="/entreprises" replace />} />
            <Route path="/profil" element={<Setup />} />
            <Route path="/entreprises" element={<Companies />} />
            <Route path="/entreprises/:id" element={<CompanyDetail />} />
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

  const handleLogout = async () => {
    await api.logout();
    setAuthed(false);
  };

  return (
    <ToastProvider>
      {authed ? <Shell onLogout={handleLogout} /> : <Login onSuccess={() => setAuthed(true)} />}
    </ToastProvider>
  );
}
