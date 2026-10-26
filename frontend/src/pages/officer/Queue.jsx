import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client.js";
import Layout, { PageHeader } from "../../components/Layout.jsx";
import { ExpiryForecast, SeniorOverview, StatTile, TimeSaved } from "../../components/Insights.jsx";
import { AlertsPanel } from "../../components/ReviewTools.jsx";
import { Badge, Card, Empty, ErrorText, formatDate, table } from "../../components/ui.jsx";

const FILTERS = ["all", "submitted", "under_scrutiny", "escalated", "returned_for_correction", "scrutiny_complete"];
const TILES = [
  ["submitted", "Submitted"], ["under_scrutiny", "Under scrutiny"], ["escalated", "Escalated"],
  ["returned_for_correction", "Returned"], ["scrutiny_complete", "Complete"], ["open_findings", "Open findings"],
];

// Scrutiny queue for officers and senior authorities. `basePath` is /officer or /senior.
export default function Queue({ title, basePath, defaultFilter = "all", senior = false }) {
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
      <PageHeader title={title} subtitle="Automated findings support your review. You make every decision." />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {TILES.map(([k, label]) => <StatTile key={k} label={label} value={counts[k] ?? 0} />)}
      </div>

      {senior && <Card title="Overview" className="mt-6"><SeniorOverview /></Card>}

      <Card title="Applications" className="mt-6"
        actions={<span className="text-xs text-slate-400" title="Weighted count of open issues. Not a probability.">Sorted by review priority</span>}>
        <div className="-mt-1 mb-4 flex flex-wrap gap-1 border-b border-slate-100 pb-3">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`rounded-md px-3 py-1.5 text-sm capitalize ${filter === f ? "bg-brand-50 font-medium text-brand-800" : "text-slate-600 hover:bg-slate-50"}`}>
              {f === "returned_for_correction" ? "returned" : f.replaceAll("_", " ")}
            </button>
          ))}
        </div>
        <ErrorText error={error} />
        {!apps && <Empty>Loading...</Empty>}
        {apps?.length === 0 && <Empty>No applications in this view.</Empty>}
        {apps?.length > 0 && (
          <div className={table.wrap}>
            <table className={table.table}>
              <thead className={table.head}>
                <tr>
                  <th className={table.th} title="Review priority: weighted count of open issues, not a probability">Priority</th>
                  <th className={table.th}>Institution</th><th className={table.th}>Status</th>
                  <th className={table.th}>Open</th><th className={table.th}>Critical</th>
                  <th className={table.th}>Submitted</th><th />
                </tr>
              </thead>
              <tbody>
                {apps.map((a) => (
                  <tr key={a.id} className={table.row}>
                    <td className={table.td}>
                      <span className={`inline-block min-w-9 rounded-md px-2 py-0.5 text-center text-xs font-semibold ${a.priority_score >= 40 ? "bg-red-50 text-red-700" : a.priority_score >= 15 ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
                        {a.priority_score ?? "-"}
                      </span>
                    </td>
                    <td className={table.td}>
                      <div className="font-medium text-slate-800">{a.institution_name.replace("SYNTHETIC ", "")}</div>
                      <div className="text-xs text-slate-400">{a.category === "eoa_increase_intake" ? "Increase in intake" : "No change"}</div>
                    </td>
                    <td className={table.td}><Badge value={a.status} /></td>
                    <td className={table.td}>{a.open_findings}</td>
                    <td className={table.td}>{a.critical_findings > 0 ? <span className="font-medium text-red-700">{a.critical_findings}</span> : <span className="text-slate-300">0</span>}</td>
                    <td className={`${table.td} text-slate-500`}>{formatDate(a.submitted_at)}</td>
                    <td className={`${table.td} text-right`}>
                      <Link className="font-medium text-brand-700 hover:underline" to={`${basePath}/applications/${a.id}`}>Review</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Alerts"><AlertsPanel appBasePath={basePath} /></Card>
        <Card title="Expiry forecast"><ExpiryForecast basePath={basePath} /></Card>
        <Card title="Time saved"><TimeSaved /></Card>
      </div>
    </Layout>
  );
}
