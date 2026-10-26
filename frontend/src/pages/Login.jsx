import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ROLE_HOME, useAuth } from "../auth/AuthContext.jsx";
import { Footer, Logo } from "../components/Layout.jsx";

const POINTS = [
  ["Pre-validate", "Missing, expired and inconsistent documents found before review."],
  ["Verify", "Certificates compared with issuer records, field by field."],
  ["Explain", "Every finding shows the evidence on the page."],
];

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />;

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const u = await login(email, password);
      navigate(ROLE_HOME[u.role], { replace: true });
    } catch (err) {
      setError(err.message || "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  const input = "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100";

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <div className="grid flex-1 lg:grid-cols-2">
        <div className="hidden flex-col justify-between bg-brand-950 p-12 text-white lg:flex">
          <Logo light />
          <div>
            <h1 className="text-3xl font-semibold leading-snug">Faster, consistent scrutiny of approval applications.</h1>
            <ul className="mt-8 space-y-5">
              {POINTS.map(([title, text]) => (
                <li key={title} className="flex gap-3">
                  <span className="mt-1 h-2 w-2 flex-none rounded-full bg-brand-100" />
                  <span><span className="font-medium">{title}.</span> <span className="text-brand-100">{text}</span></span>
                </li>
              ))}
            </ul>
          </div>
          <p className="text-xs text-brand-100">Decision support only. Authorised officials make every decision.</p>
        </div>

        <div className="flex items-center justify-center px-6 py-12">
          <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5">
            <div className="lg:hidden"><Logo /></div>
            <div>
              <h2 className="text-2xl font-semibold">Sign in</h2>
              <p className="mt-1 text-sm text-slate-500">Use your Validex account.</p>
            </div>
            <label className="block text-sm font-medium text-slate-700">
              Email
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={input} />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Password
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className={input} />
            </label>
            {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <button type="submit" disabled={busy}
              className="w-full rounded-md bg-brand-700 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-brand-800 disabled:opacity-50">
              {busy ? "Signing in..." : "Sign in"}
            </button>
            <p className="text-center text-xs text-slate-400">Demo accounts only · synthetic data</p>
          </form>
        </div>
      </div>
      <Footer />
    </div>
  );
}
