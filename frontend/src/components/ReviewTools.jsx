// Staff-only panels: issuer verification (submitted vs source), review priority, alerts.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { Badge, Button, Empty, ErrorText, Tag, formatDate, useAsync } from "./ui.jsx";

const VERIFICATION_STYLE = {
  verified: "bg-emerald-100 text-emerald-800",
  mismatch: "bg-red-100 text-red-800",
  expired: "bg-red-100 text-red-800",
  pending: "bg-sky-100 text-sky-800",
  source_unavailable: "bg-amber-100 text-amber-800",
  manual_review: "bg-amber-100 text-amber-800",
};

function VerificationStatus({ status }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${VERIFICATION_STYLE[status]}`}>{status.replaceAll("_", " ")}</span>;
}

export function VerificationPanel({ verifications, canVerify, onChanged }) {
  const { busy, error, run } = useAsync();
  if (!verifications?.length) return <Empty>No documents to verify yet.</Empty>;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-xs text-slate-500"><Tag>Mock issuers</Tag> Simulated registries, no live system is contacted.</div>
      <ErrorText error={error} />
      {verifications.map((v) => {
        const fields = [...new Set([...Object.keys(v.submitted_values || {}), ...Object.keys(v.source_values || {})])];
        const bad = new Set((v.mismatches || []).map((m) => m.field));
        return (
          <div key={v.id} className="rounded-lg border border-slate-200 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium capitalize">{v.doc_type.replaceAll("_", " ")}</span>
              <VerificationStatus status={v.status} />
              <span className="text-xs text-slate-400">{v.source.replace("MOCK ", "")} · {v.reference_submitted || "no reference"}</span>
              {canVerify && (
                <Button variant="secondary" className="ml-auto" disabled={busy}
                  onClick={() => run(async () => { await api(`/documents/${v.document_id}/verify`, { method: "POST" }); onChanged(); })}>
                  Re-verify
                </Button>
              )}
            </div>
            {v.error && <p className="mt-1 text-sm text-amber-800">{v.error}</p>}
            {fields.length > 0 && (
              <table className="mt-2 w-full text-sm">
                <thead className="text-left text-xs text-slate-500">
                  <tr><th className="py-1">Field</th><th>Submitted</th><th>Issuer record</th><th /></tr>
                </thead>
                <tbody>
                  {fields.map((f) => (
                    <tr key={f} className={`border-t border-slate-100 ${bad.has(f) ? "bg-red-50" : ""}`}>
                      <td className="py-1 pr-2 text-slate-500">{f.replaceAll("_", " ")}</td>
                      <td className="pr-2">{v.submitted_values?.[f] ?? "-"}</td>
                      <td className="pr-2">{v.source_values?.[f] ?? "-"}</td>
                      <td className="text-xs">{bad.has(f) ? <span className="text-red-700">differs</span> : v.source_values?.[f] ? <span className="text-emerald-700">matches</span> : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function PriorityPanel({ priority }) {
  if (!priority) return null;
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-semibold">{priority.score}</span>
        <span className="text-sm text-slate-400">/ {priority.max}</span>
      </div>
      <p className="mt-1 text-xs text-slate-400">Ordering aid. Not a probability.</p>
      <table className="mt-2 w-full text-sm">
        <tbody>
          {priority.factors.map((f) => (
            <tr key={f.factor} className="border-t border-slate-100">
              <td className="py-1">{f.factor}</td>
              <td className="text-xs text-slate-500">{f.detail}</td>
              <td className="text-right font-medium">+{f.points}</td>
            </tr>
          ))}
          {priority.factors.length === 0 && <tr><td className="py-1 text-slate-400">No open issues.</td></tr>}
        </tbody>
      </table>
      {priority.raw_points > priority.max && <p className="mt-1 text-xs text-slate-500">Raw total {priority.raw_points}, capped at {priority.max}.</p>}
    </div>
  );
}

const KIND_LABEL = {
  missing: "Missing document",
  expired: "Expired document",
  pending_verification: "Verification pending too long",
  anomaly: "Anomaly indicator",
  awaiting_correction: "Awaiting correction",
};

export function AlertsPanel({ appBasePath }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const load = () => api("/notifications").then(setItems).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function markRead(id) {
    await api(`/notifications/${id}/read`, { method: "POST" });
    load();
  }

  if (error) return <ErrorText error={error} />;
  if (!items) return <Empty>Loading...</Empty>;
  const unread = items.filter((n) => !n.read_at);
  if (!unread.length) return <Empty>No new alerts.</Empty>;
  return (
    <ul className="divide-y divide-slate-100">
      {unread.slice(0, 8).map((n) => (
        <li key={n.id} className="flex items-start gap-2 py-2.5 text-sm">
          <span className="flex-1">
            <span className="block text-xs font-semibold uppercase tracking-wide text-slate-500">{KIND_LABEL[n.kind] || n.kind}</span>
            {n.message.replaceAll("SYNTHETIC ", "")}
            {n.application_id && appBasePath && (
              <> · <Link className="font-medium text-brand-700 hover:underline" to={`${appBasePath}/applications/${n.application_id}`}>Open</Link></>
            )}
          </span>
          <button className="text-xs text-slate-400 hover:text-slate-700" title="Mark as read" onClick={() => markRead(n.id)}>Dismiss</button>
        </li>
      ))}
    </ul>
  );
}
