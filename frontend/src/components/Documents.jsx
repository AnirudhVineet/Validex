import { useState } from "react";
import { api, openDocument } from "../api/client.js";
import { Badge, Button, ErrorText } from "./ui.jsx";

function FieldRow({ field, canCorrect, onChanged }) {
  const isAi = field.source === "ai_vision";
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(field.value || "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  async function save(e) {
    e.preventDefault();
    setError("");
    try {
      await api(`/fields/${field.id}`, { method: "PATCH", body: { value, reason } });
      setEditing(false);
      onChanged?.();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <tr className="border-t border-slate-100 align-top">
      <td className="py-1 pr-3 text-slate-500">{field.field_name.replaceAll("_", " ")}</td>
      <td className="py-1 pr-3">
        {editing ? (
          <form onSubmit={save} className="space-y-1">
            <input value={value} onChange={(e) => setValue(e.target.value)} className="w-full rounded border px-2 py-1" />
            <input
              value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason for correction (required)"
              className="w-full rounded border px-2 py-1"
            />
            <ErrorText error={error} />
            <div className="flex gap-2">
              <Button type="submit" disabled={reason.trim().length < 5}>Save</Button>
              <Button type="button" variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          </form>
        ) : (
          <span className="break-all">{field.value}</span>
        )}
      </td>
      <td className="py-1 pr-3 text-xs text-slate-500">
        {field.source} · {Math.round(field.confidence * 100)}%{field.page ? ` · p${field.page}` : ""}
        {isAi && <span className="ml-1 rounded bg-violet-100 px-1 text-violet-800">AI-read suggestion</span>}
        {field.needs_confirmation && <span className="ml-1 text-amber-700">needs confirmation</span>}
      </td>
      <td className="py-1 text-right">
        {canCorrect && !editing && isAi && (
          <button className="mr-2 text-xs font-medium text-violet-700 hover:underline"
            onClick={() => { setValue(field.value || ""); setReason("Checked against the document image"); setEditing(true); }}>
            Confirm
          </button>
        )}
        {canCorrect && !editing && (
          <button className="text-xs text-sky-700 hover:underline" onClick={() => setEditing(true)}>Correct</button>
        )}
      </td>
    </tr>
  );
}

export function DocumentPanel({ doc, canCorrect, onChanged }) {
  const [error, setError] = useState("");
  return (
    <div className="rounded border border-slate-200 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium capitalize">{doc.doc_type.replaceAll("_", " ")}</span>
        <Badge value={doc.status} />
        {doc.extraction_method && <span className="text-xs text-slate-500">via {doc.extraction_method}</span>}
        {doc.classified_type && doc.classified_type !== doc.doc_type && (
          <span className="text-xs text-amber-700">looks like: {doc.classified_type.replaceAll("_", " ")}</span>
        )}
        <button
          className="ml-auto text-sm text-sky-700 hover:underline"
          onClick={() => openDocument(doc.id).catch((e) => setError(e.message))}
        >
          View file
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {doc.original_filename} · SHA-256 {doc.sha256.slice(0, 16)}…
      </p>
      {doc.extraction_error && <p className="mt-2 text-sm text-red-700">{doc.extraction_error}</p>}
      <ErrorText error={error} />
      {doc.fields?.length > 0 && (
        <table className="mt-2 w-full text-sm">
          <tbody>
            {doc.fields.map((f) => (
              <FieldRow key={f.id} field={f} canCorrect={canCorrect} onChanged={onChanged} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
