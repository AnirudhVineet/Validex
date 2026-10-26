import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";

const NAV = {
  applicant: [["/applicant", "Applications"]],
  scrutiny_officer: [["/officer", "Queue"], ["/officer/rules", "Rules"]],
  senior_authority: [["/senior", "Overview"], ["/senior/rules", "Rules"]],
  inspector: [["/inspector", "Flagged cases"]],
  admin: [["/admin", "Audit"], ["/admin/rules", "Rules"]],
};

export const ROLE_LABEL = {
  applicant: "Applicant",
  scrutiny_officer: "Scrutiny Officer",
  senior_authority: "Senior Authority",
  inspector: "Inspector",
  admin: "Administrator",
};

export function Logo({ light = false }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">
        <rect width="32" height="32" rx="7" className={light ? "fill-white/15" : "fill-brand-800"} />
        <path d="M9 16.5l4.5 4.5L23 11.5" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-wide">VALIDEX</div>
        <div className={`text-[11px] ${light ? "text-brand-100" : "text-slate-500"}`}>Application Scrutiny Platform</div>
      </div>
    </div>
  );
}

export function Footer() {
  return (
    <footer className="mt-auto border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap justify-between gap-2 px-6 py-3 text-xs text-slate-500">
        <span>© Validex · Prototype, not an official AICTE system</span>
        <span>Synthetic data · Decisions are made by authorised officials</span>
      </div>
    </footer>
  );
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="bg-brand-950 text-white shadow">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-10">
            <Logo light />
            {user && (
              <nav className="hidden gap-1 text-sm sm:flex">
                {(NAV[user.role] || []).map(([to, label]) => (
                  <NavLink
                    key={to} to={to} end
                    className={({ isActive }) =>
                      `rounded px-3 py-2 ${isActive ? "bg-white/10 font-medium text-white" : "text-brand-100 hover:bg-white/5 hover:text-white"}`}
                  >
                    {label}
                  </NavLink>
                ))}
              </nav>
            )}
          </div>
          {user && (
            <div className="flex items-center gap-4 text-sm">
              <div className="text-right leading-tight">
                <div className="font-medium">{user.name}</div>
                <div className="text-xs text-brand-100">{ROLE_LABEL[user.role]}</div>
              </div>
              <button onClick={logout} className="rounded border border-white/30 px-3 py-1.5 text-xs hover:bg-white/10">
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">{children}</main>
      <Footer />
    </div>
  );
}

// Page title row used by every page: optional back link, title, subtitle, right-side content.
export function PageHeader({ title, subtitle, children, back }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        {back}
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-500">{subtitle}</div>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-3">{children}</div>}
    </div>
  );
}
