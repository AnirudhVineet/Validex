import { useAuth } from "../auth/AuthContext.jsx";

export const ROLE_LABEL = {
  applicant: "Applicant",
  scrutiny_officer: "Scrutiny Officer",
  senior_authority: "Senior Authority",
  inspector: "Inspector",
  admin: "Admin",
};

export function Footer() {
  return (
    <footer className="mt-auto border-t border-slate-200 bg-white px-6 py-3 text-xs text-slate-500">
      Validex is a hackathon prototype, not an official AICTE system. Decision support only:
      authorised officials make every final decision. All data shown is SYNTHETIC.
    </footer>
  );
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div className="font-semibold">
          Validex <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">PROTOTYPE</span>
        </div>
        {user && (
          <div className="flex items-center gap-4 text-sm">
            <span>
              {user.name} <span className="text-slate-500">({ROLE_LABEL[user.role]})</span>
            </span>
            <button onClick={logout} className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100">
              Log out
            </button>
          </div>
        )}
      </header>
      <main className="flex-1 px-6 py-6">{children}</main>
      <Footer />
    </div>
  );
}
