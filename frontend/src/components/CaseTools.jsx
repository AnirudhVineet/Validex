// Phase 3 case tools: deficiency letter draft, optional grounded summary, inspection + advisory.
import { useEffect, useState } from "react";
import { api, openDocument } from "../api/client.js";
import { Badge, Button, ErrorText, Notice, formatDate, useAsync } from "./ui.jsx";

export function LetterPanel({ app, canReturn, onReturned }) {
  const [text, setText] = useState("");
  const { busy, error, run } = useAsync();
  return (
    <div className="space-y-2">
      <Notice>Template-based draft (no AI). Uses only findings the applicant can see. Edit before sending.</Notice>
      {!text && <Button variant="secondary" disabled={busy} onClick={() => run(async () => {
        setText((await api(`/applications/${app.id}/deficiency-letter`, { method: "POST" })).text);
      })}>Draft deficiency letter</Button>}
      {text && (
        <>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={14}
            className="w-full rounded border border-slate-300 p-2 font-mono text-xs" />
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => navigator.clipboard?.writeText(text)}>Copy</Button>
            {canReturn && (
              <Button disabled={busy || text.trim().length < 5} onClick={() => run(async () => {
                await api(`/applications/${app.id}/decision`, { method: "POST", body: { decision: "return_for_correction", reason: text } });
                setText("");
                onReturned();
              })}>Return for correction with this letter</Button>
            )}
          </div>
        </>
      )}
      <ErrorText error={error} />
    </div>
  );
}

export function SummaryPanel({ app, findings }) {
  const [data, setData] = useState(null);
  const { busy, error, run } = useAsync();
  const titles = Object.fromEntries((findings || []).map((f) => [f.id, `${f.rule_id}`]));
  return (
    <div className="space-y-2">
      <Notice>Optional AI summary (disabled by default). Every point must cite finding ids; it never changes validation results.</Notice>
      <Button variant="secondary" disabled={busy} onClick={() => run(async () => setData(await api(`/applications/${app.id}/summary`, { method: "POST" })))}>
        {busy ? "Summarising..." : "Generate summary"}
      </Button>
      <ErrorText error={error} />
      {data && !data.enabled && <p className="text-sm text-slate-500">{data.note}</p>}
      {data?.enabled && (data.insufficient_evidence
        ? <p className="text-sm text-slate-600">Insufficient evidence for a summary. {data.note}</p>
        : (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {data.points.map((p) => (
              <li key={p.text}>{p.text} <span className="text-xs text-slate-500">[{p.finding_ids.map((i) => titles[i] || i.slice(0, 8)).join(", ")}]</span></li>
            ))}
          </ul>
        ))}
      {data?.enabled && <p className="text-xs text-slate-500">Model: {data.model}{data.dropped_points ? ` · ${data.dropped_points} uncited point(s) removed` : ""}</p>}
    </div>
  );
}

function InspectionForm({ app, items, onSaved }) {
  const [notes, setNotes] = useState("");
  const [label, setLabel] = useState(items[0]?.key || "");
  const [file, setFile] = useState(null);
  const { busy, error, run } = useAsync();
  async function submit(e) {
    e.preventDefault();
    const form = new FormData();
    form.append("notes", notes);
    if (file) {
      form.append("evidence_label", label);
      form.append("file", file);
    }
    await run(async () => {
      await api(`/applications/${app.id}/inspections`, { method: "POST", form });
      setNotes("");
      setFile(null);
      e.target.reset();
      onSaved();
    });
  }
  return (
    <form onSubmit={submit} className="space-y-2 rounded border border-slate-200 p-3">
      <label className="block text-sm">Notes
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className="mt-1 w-full rounded border px-2 py-1" />
      </label>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-sm">Evidence label
          <select value={label} onChange={(e) => setLabel(e.target.value)} className="mt-1 block rounded border px-2 py-1">
            {items.map((i) => <option key={i.key} value={i.key}>{i.label}</option>)}
          </select>
        </label>
        <input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] || null)} className="text-sm" />
        <Button type="submit" disabled={busy || (!notes.trim() && !file)}>Save inspection record</Button>
      </div>
      <ErrorText error={error} />
    </form>
  );
}

export function InspectionPanel({ app, canAdd }) {
  const [records, setRecords] = useState([]);
  const [advisory, setAdvisory] = useState(null);
  const [error, setError] = useState("");
  const load = () => {
    api(`/applications/${app.id}/inspections`).then(setRecords).catch((e) => setError(e.message));
    api(`/applications/${app.id}/infrastructure`).then(setAdvisory).catch((e) => setError(e.message));
  };
  useEffect(load, [app.id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-3">
      <ErrorText error={error} />
      {advisory && (
        <div>
          <p className="text-xs text-slate-500">{advisory.notice}</p>
          <ul className="mt-2 space-y-1 text-sm">
            {advisory.items.map((i) => (
              <li key={i.key} className="flex items-center justify-between gap-2">
                <span>{i.label}</span>
                <span className="flex items-center gap-2 text-xs">
                  {i.labels_read_from_evidence.length > 0 && <span className="text-slate-500">read: {i.labels_read_from_evidence.join(", ")}</span>}
                  {i.present ? <Badge value={`evidence present (${i.evidence_files})`} /> : <span className="text-slate-400">no evidence yet</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {canAdd && advisory && <InspectionForm app={app} items={advisory.items} onSaved={load} />}
      <ul className="space-y-2 text-sm">
        {records.map((r) => (
          <li key={r.id} className="rounded border border-slate-100 p-2">
            <div className="text-xs text-slate-500">{formatDate(r.created_at)}{r.evidence_label && ` · ${r.evidence_label.replaceAll("_", " ")}`}</div>
            {r.notes && <p>{r.notes}</p>}
            {r.evidence_document_id && (
              <button className="text-xs text-sky-700 hover:underline" onClick={() => openDocument(r.evidence_document_id).catch((e) => setError(e.message))}>
                View evidence file
              </button>
            )}
          </li>
        ))}
        {records.length === 0 && <li className="text-slate-500">No inspection records.</li>}
      </ul>
    </div>
  );
}
