import { NavLink } from "react-router-dom";
import { IconBuilding, IconUserCircle, IconLogOut, IconX } from "./Icons.jsx";

const links = [
  { to: "/entreprises", label: "Entreprises", icon: IconBuilding },
  { to: "/profil", label: "Profil", icon: IconUserCircle },
];

export default function Sidebar({ open, onClose, onLogout }) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-slate-900 border-r border-slate-800
          flex flex-col transition-transform duration-200 ease-out
          md:translate-x-0 md:sticky md:top-0 md:h-screen
          ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex items-center justify-between gap-2 px-4 h-16 shrink-0 border-b border-slate-800">
          <div className="flex items-center gap-2 font-display font-bold text-white">
            <img src="/logo.png" alt="CandidAI" className="w-8 h-8 rounded-lg shadow-sm" />
            <span className="text-[16px] leading-tight">CandidAI</span>
          </div>
          <button onClick={onClose} className="md:hidden p-1.5 rounded-lg text-slate-400 hover:bg-slate-800">
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

        <div className="p-3 border-t border-slate-800">
          <button onClick={onLogout} className="nav-link w-full">
            <IconLogOut className="w-[18px] h-[18px]" />
            Déconnexion
          </button>
        </div>
      </aside>
    </>
  );
}
