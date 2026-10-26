import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ROLE_HOME, useAuth } from "../auth/AuthContext.jsx";
import { Footer } from "../components/Layout.jsx";

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
      setError(err.message || "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex flex-1 items-center justify-center px-4">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div>
            <h1 className="text-xl font-semibold">VerifyAI</h1>
            <p className="text-sm text-slate-500">AI-assisted document pre-validation (prototype)</p>
          </div>
          <label className="block text-sm">
            Email
            <input
              type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            Password
            <input
              type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            />
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit" disabled={busy}
            className="w-full rounded bg-slate-900 py-2 text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {busy ? "Signing in..." : "Sign in"}
          </button>
          <p className="text-xs text-slate-500">Demo accounts are SYNTHETIC. See README for credentials.</p>
        </form>
      </div>
      <Footer />
    </div>
  );
}
