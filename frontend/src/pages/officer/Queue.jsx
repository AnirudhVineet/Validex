import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import Layout from "../../components/Layout.jsx";
import { AlertsPanel } from "../../components/ReviewTools.jsx";
import { Badge, Card, ErrorText, formatDate } from "../../components/ui.jsx";

const FILTERS = ["all", "submitted", "under_scrutiny", "escalated", "returned_for_correction", "scrutiny_complete"];

// Scrutiny queue for officers and senior authorities. `basePath` is /officer or /senior.
export default function Queue({ title, basePath, defaultFilter = "all" }) {
  const [filter, setFilter] = useState(defaultFilter);
  const [apps, setApps] = useState(null);
  const [counts, setCounts] = useState({});
  const [error, setError] = useState("");

  useEffect(() => {
    api("/dashboard").then((d) => setCounts(d.counts)).catch(() => {});
  }, []);

  useEffect(() => {
    setApps(null);
    const query = filter === "all" ? "" : `?status=${filter}`;
    api(`/applications${query}`).then(setApps).catch((e) => setError(e.message));
  }, [filter]);

  return (
    <Layout>
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="mt-1 text-slate-600">Automated findings are decision support. You make every decision.</p>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {["submitted", "under_scrutiny", "escalated", "returned_for_correction", "scrutiny_complete", "open_findings"].map((k) => (
          <div key={k} className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="text-xs capitalize text-slate-500">{k.replaceAll("_", " ")}</div>
            <div className="text-xl font-semibold">{counts[k] ?? 0}</div>
          </div>
        ))}
      </div>

      <Card title="Alerts" className="mt-4"><AlertsPanel appBasePath={basePath} /></Card>

      <div className="mt-4 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f} onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1 text-sm ${filter === f ? "bg-slate-900 text-white" : "border border-slate-300 bg-white"}`}
          >
            {f.replaceAll("_", " ")}
          </button>
        ))}
      </div>
      <ErrorText error={error} />

      <Card className="mt-3">
        {!apps && <p className="text-sm text-slate-500">Loading...</p>}
        {apps?.length === 0 && <p className="text-sm text-slate-500">Nothing in this view.</p>}
        {apps?.length > 0 && <p className="mb-2 text-xs text-slate-500">Sorted by review priority: a weighted count of open issues (breakdown on each case). Not a probability.</p>}
        {apps?.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr><th className="py-1" title="Review-priority aid, not a probability">Priority</th><th>Institution</th><th>Category</th><th>Status</th><th>Open findings</th><th>Critical</th><th>Submitted</th><th /></tr>
            </thead>
            <tbody>
              {apps.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  <td className="py-2 font-medium">{a.priority_score ?? "-"}</td>
                  <td>{a.institution_name}</td>
                  <td>{a.category.replaceAll("_", " ")}</td>
                  <td><Badge value={a.status} /></td>
                  <td>{a.open_findings}</td>
                  <td>{a.critical_findings > 0 ? <Badge value="critical" kind="severity" /> : "-"} {a.critical_findings || ""}</td>
                  <td>{formatDate(a.submitted_at)}</td>
                  <td className="text-right"><Link className="text-sky-700 hover:underline" to={`${basePath}/applications/${a.id}`}>Review</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </Layout>
  );
}
