import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import Layout, { ROLE_LABEL } from "../components/Layout.jsx";

// Phase 0: one generic dashboard per role, backed by GET /api/dashboard.
// Each role gets its own page in Phase 1+ (applicant checklist, officer queue, ...).
const ROLE_INTRO = {
  applicant: "Your applications, checklist progress and pre-check findings will appear here.",
  scrutiny_officer: "Your scrutiny queue, statuses and open deficiencies will appear here.",
  senior_authority: "Escalated cases and summary counts will appear here.",
  inspector: "Flagged cases and inspection notes will appear here.",
  admin: "Users, rule versions and the audit log will appear here.",
};

function prettify(key) {
  return key.replaceAll("_", " ");
}

export default function Dashboard({ role }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/dashboard").then(setData).catch((e) => setError(e.message));
  }, []);

  return (
    <Layout>
      <h1 className="text-2xl font-semibold">{ROLE_LABEL[role]} dashboard</h1>
      <p className="mt-1 text-slate-600">{ROLE_INTRO[role]}</p>

      {error && <p className="mt-4 text-red-600">{error}</p>}
      {!data && !error && <p className="mt-4 text-slate-500">Loading...</p>}
      {data && (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {Object.entries(data.counts).map(([key, value]) => (
            <div key={key} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="text-sm capitalize text-slate-500">{prettify(key)}</div>
              <div className="mt-1 text-2xl font-semibold">{value}</div>
            </div>
          ))}
          {Object.keys(data.counts).length === 0 && <p className="text-slate-500">Nothing yet.</p>}
        </div>
      )}
    </Layout>
  );
}
