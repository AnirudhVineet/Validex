// Staff dashboard widgets: expiry forecast, time saved, senior overview.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { Badge, ErrorText } from "./ui.jsx";

const BAR_COLOR = "#2a78d6"; // single series: one hue (reference palette slot 1)

// Horizontal single-series bars. Values are printed in text ink; the bar carries magnitude only.
// Each row shows a tooltip on hover/focus with the exact value.
export function BarList({ rows, unit = "" }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (!rows.length) return <p className="text-sm text-slate-500">No data yet.</p>;
  return (
    <ul className="space-y-2" role="list">
      {rows.map((r) => (
        <li
          key={r.label} className="relative grid grid-cols-[minmax(8rem,14rem)_1fr_2.5rem] items-center gap-3 py-1 text-sm"
          onMouseEnter={() => setHover(r.label)} onMouseLeave={() => setHover(null)}
          onFocus={() => setHover(r.label)} onBlur={() => setHover(null)} tabIndex={0}
        >
          <span className="truncate text-slate-700" title={r.label}>{r.label}</span>
          <span className="h-3 rounded-r bg-slate-100">
            <span
              className="block h-3 rounded-r-[4px]"
              style={{ width: `${(r.value / max) * 100}%`, minWidth: r.value ? "4px" : 0, background: BAR_COLOR }}
            />
          </span>
          <span className="text-right tabular-nums text-slate-900">{r.value}</span>
          {hover === r.label && (
            <span className="pointer-events-none absolute -top-7 left-40 z-10 rounded bg-slate-900 px-2 py-1 text-xs text-white shadow">
              {r.tooltip || `${r.label}: ${r.value}${unit}`}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

export function StatTile({ label, value, note }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      {note && <div className="mt-1 text-xs text-slate-500">{note}</div>}
    </div>
  );
}

export function ExpiryForecast({ basePath }) {
  const [days, setDays] = useState(90);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api(`/dashboard/expiry-forecast?days=${days}`).then(setData).catch((e) => setError(e.message));
  }, [days]);

  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-sm">
        <span className="text-slate-600">Window</span>
        {[30, 90, 180].map((d) => (
          <button key={d} onClick={() => setDays(d)}
            className={`rounded-full px-2.5 py-0.5 ${days === d ? "bg-slate-900 text-white" : "border border-slate-300"}`}>
            {d} days
          </button>
        ))}
      </div>
      <ErrorText error={error} />
      {data && (data.items.length === 0
        ? <p className="text-sm text-slate-500">No documents expiring within {days} days.</p>
        : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr><th className="py-1">Institution</th><th>Document</th><th>Expiry</th><th>Days left</th><th /></tr>
            </thead>
            <tbody>
              {data.items.map((i) => (
                <tr key={`${i.application_id}${i.doc_type}`} className="border-t border-slate-100">
                  <td className="py-1">{i.institution}</td>
                  <td>{i.doc_type.replaceAll("_", " ")}</td>
                  <td className="tabular-nums">{i.expiry_date}</td>
                  <td className="tabular-nums">
                    {i.days_left < 0
                      ? <span className="text-red-700">expired {-i.days_left} d ago</span>
                      : i.days_left}
                  </td>
                  <td className="text-right">
                    {basePath && <Link className="text-sky-700 hover:underline" to={`${basePath}/applications/${i.application_id}`}>open</Link>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
    </div>
  );
}

export function TimeSaved() {
  const [data, setData] = useState(null);
  useEffect(() => { api("/dashboard/time-saved").then(setData).catch(() => {}); }, []);
  if (!data) return null;
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-semibold tabular-nums">~{data.hours} h</span>
        <span className="text-sm text-slate-500">estimated officer time saved</span>
      </div>
      <p className="mt-1 text-xs text-slate-600">
        {data.inputs.documents_auto_checked} documents auto-checked · {data.inputs.issuer_verifications} issuer lookups · {data.inputs.official_validation_runs} validation runs
      </p>
      <p className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-900">{data.assumption}</p>
    </div>
  );
}

export function SeniorOverview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/dashboard/senior").then(setData).catch((e) => setError(e.message)); }, []);
  if (error) return <ErrorText error={error} />;
  if (!data) return <p className="text-sm text-slate-500">Loading overview...</p>;
  const counts = data.status_counts;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div>
        <h3 className="mb-2 text-sm font-medium">Applications by status</h3>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(counts).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between rounded border border-slate-100 px-2 py-1 text-sm">
              <Badge value={k} /> <span className="tabular-nums">{v}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">Ageing of open cases (days since submission)</h3>
        <BarList rows={Object.entries(data.ageing).map(([label, value]) => ({
          label, value, tooltip: `${value} open case(s) submitted ${label} ago` }))} />
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">Most common open findings (applications affected)</h3>
        <BarList rows={data.common_deficiencies.map((d) => ({
          label: `${d.rule_id} ${d.description}`, value: d.applications,
          tooltip: `${d.rule_id}: ${d.description} - ${d.applications} application(s)` }))} />
      </div>
    </div>
  );
}
