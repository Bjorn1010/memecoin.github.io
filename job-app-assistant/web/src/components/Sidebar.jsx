import { NavLink } from "react-router-dom";
import { IconBuilding, IconUserCircle, IconLogOut, IconSparkles, IconX } from "./Icons.jsx";

const links = [
  { to: "/entreprises", label: "Entreprises", icon: IconBuilding },
  { to: "/profil", label: "Profil", icon: IconUserCircle },
];

export default function Sidebar({ open, onClose, onLogout }) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 bg-slate-900/30 z-30 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-slate-200
          flex flex-col transition-transform duration-200 ease-out
          md:translate-x-0 md:sticky md:top-0 md:h-screen
          ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex items-center justify-between gap-2 px-4 h-16 shrink-0 border-b border-slate-100">
          <div className="flex items-center gap-2 font-display font-bold text-slate-900">
            <span className="grid place-items-center w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm">
              <IconSparkles className="w-4 h-4" />
            </span>
            <span className="text-[15px] leading-tight">Assistant Candidatures</span>
          </div>
          <button onClick={onClose} className="md:hidden p-1.5 rounded-lg text-slate-400 hover:bg-slate-100">
            <IconX className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}
            >
              <Icon className="w-[18px] h-[18px]" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-slate-100">
          <button onClick={onLogout} className="nav-link w-full text-slate-500">
            <IconLogOut className="w-[18px] h-[18px]" />
            Déconnexion
          </button>
        </div>
      </aside>
    </>
  );
}
