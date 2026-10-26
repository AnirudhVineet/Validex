// Small shared UI pieces. Plain Tailwind, no component library.
import { useState } from "react";

export function Card({ title, actions, children, className = "" }) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="font-semibold">{title}</h2>
          <div className="flex gap-2">{actions}</div>
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

const BUTTON_STYLES = {
  primary: "bg-slate-900 text-white hover:bg-slate-700",
  secondary: "border border-slate-300 bg-white hover:bg-slate-100",
  warn: "bg-amber-600 text-white hover:bg-amber-500",
  danger: "bg-red-700 text-white hover:bg-red-600",
};

export function Button({ variant = "primary", className = "", ...props }) {
  return (
    <button
      {...props}
      className={`rounded px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_STYLES[variant]} ${className}`}
    />
  );
}

const SEVERITY_STYLES = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-sky-100 text-sky-800",
  info: "bg-slate-100 text-slate-700",
};

const STATUS_STYLES = {
  draft: "bg-slate-100 text-slate-700",
  submitted: "bg-sky-100 text-sky-800",
  under_scrutiny: "bg-indigo-100 text-indigo-800",
  returned_for_correction: "bg-amber-100 text-amber-800",
  escalated: "bg-purple-100 text-purple-800",
  scrutiny_complete: "bg-emerald-100 text-emerald-800",
  open: "bg-red-50 text-red-700",
  resolved: "bg-emerald-100 text-emerald-800",
  dismissed: "bg-slate-100 text-slate-700",
  uploaded: "bg-slate-100 text-slate-700",
  processing: "bg-sky-100 text-sky-800",
  extracted: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

export function Badge({ value, kind = "status" }) {
  const styles = kind === "severity" ? SEVERITY_STYLES : STATUS_STYLES;
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${styles[value] || "bg-slate-100"}`}>
      {String(value).replaceAll("_", " ")}
    </span>
  );
}

export function ErrorText({ error }) {
  if (!error) return null;
  return <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>;
}

export function Notice({ children }) {
  return <p className="rounded bg-amber-50 px-3 py-2 text-xs text-amber-900">{children}</p>;
}

// Inline "reason required" form, used for every officer action (no browser dialogs).
export function ReasonForm({ label, variant = "primary", onSubmit, disabled }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!open) {
    return (
      <Button variant={variant} disabled={disabled} onClick={() => setOpen(true)}>
        {label}
      </Button>
    );
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSubmit(reason);
      setOpen(false);
      setReason("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex w-full flex-col gap-2 rounded border border-slate-200 bg-slate-50 p-2">
      <label className="text-xs font-medium text-slate-600">{label}: reason (required)</label>
      <textarea
        value={reason} onChange={(e) => setReason(e.target.value)} rows={2} minLength={5} required
        className="rounded border border-slate-300 px-2 py-1 text-sm"
      />
      <ErrorText error={error} />
      <div className="flex gap-2">
        <Button type="submit" variant={variant} disabled={busy || reason.trim().length < 5}>
          {busy ? "Saving..." : `Confirm: ${label}`}
        </Button>
        <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </form>
  );
}

export function formatDate(value) {
  if (!value) return "";
  return new Date(value.endsWith("Z") ? value : `${value}Z`).toLocaleString();
}

export function useAsync() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(fn) {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (err) {
      setError(err.message);
      return undefined;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, setError, run };
}
