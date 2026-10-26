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
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</div>
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
        {[30, 90, 180].map((d) => (
          <button key={d} onClick={() => setDays(d)}
            className={`rounded-md px-2.5 py-1 text-xs ${days === d ? "bg-brand-50 font-medium text-brand-800" : "text-slate-500 hover:bg-slate-50"}`}>
            {d} days
          </button>
        ))}
      </div>
      <ErrorText error={error} />
      {data && (data.items.length === 0
        ? <p className="py-4 text-center text-sm text-slate-400">Nothing expiring within {days} days.</p>
        : (
          <ul className="divide-y divide-slate-100">
            {data.items.map((i) => (
              <li key={`${i.application_id}${i.doc_type}`} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <div className="min-w-0">
                  <div className="truncate font-medium text-slate-800">
                    {basePath ? <Link className="hover:underline" to={`${basePath}/applications/${i.application_id}`}>{i.institution.replace("SYNTHETIC ", "")}</Link>
                      : i.institution.replace("SYNTHETIC ", "")}
                  </div>
                  <div className="text-xs capitalize text-slate-400">{i.doc_type.replaceAll("_", " ")} · {i.expiry_date}</div>
                </div>
                <span className={`flex-none whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ${i.days_left < 0 ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
                  {i.days_left < 0 ? `Expired ${-i.days_left} d ago` : `${i.days_left} days left`}
                </span>
              </li>
            ))}
          </ul>
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
        <span className="text-sm text-slate-500">officer time saved</span>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {data.inputs.documents_auto_checked} documents · {data.inputs.issuer_verifications} issuer checks · {data.inputs.official_validation_runs} runs
      </p>
      <p className="mt-2 text-xs text-slate-400">{data.assumption}</p>
    </div>
  );
}

export function SeniorOverview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/dashboard/senior").then(setData).catch((e) => setError(e.message)); }, []);
  if (error) return <ErrorText error={error} />;
  if (!data) return <p className="text-sm text-slate-500">Loading overview...</p>;
  return (
    <div className="grid gap-8 lg:grid-cols-2">
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
