// Shared UI pieces. Plain Tailwind, no component library.
import { useState } from "react";

export function Card({ title, actions, children, className = "" }) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white shadow-sm ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">{title}</h2>
          <div className="flex gap-2">{actions}</div>
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

const BUTTON_STYLES = {
  primary: "bg-brand-700 text-white hover:bg-brand-800",
  secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
  warn: "bg-amber-600 text-white hover:bg-amber-700",
  danger: "bg-red-700 text-white hover:bg-red-800",
};

export function Button({ variant = "primary", className = "", ...props }) {
  return (
    <button
      {...props}
      className={`rounded-md px-3.5 py-2 text-sm font-medium shadow-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_STYLES[variant]} ${className}`}
    />
  );
}

const SEVERITY_STYLES = {
  critical: "bg-red-50 text-red-700 ring-red-200",
  high: "bg-orange-50 text-orange-700 ring-orange-200",
  medium: "bg-amber-50 text-amber-700 ring-amber-200",
  low: "bg-sky-50 text-sky-700 ring-sky-200",
  info: "bg-slate-50 text-slate-600 ring-slate-200",
};

const STATUS_STYLES = {
  draft: "bg-slate-50 text-slate-600 ring-slate-200",
  submitted: "bg-sky-50 text-sky-700 ring-sky-200",
  under_scrutiny: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  returned_for_correction: "bg-amber-50 text-amber-700 ring-amber-200",
  escalated: "bg-purple-50 text-purple-700 ring-purple-200",
  scrutiny_complete: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  open: "bg-red-50 text-red-700 ring-red-200",
  resolved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  dismissed: "bg-slate-50 text-slate-600 ring-slate-200",
  uploaded: "bg-slate-50 text-slate-600 ring-slate-200",
  processing: "bg-sky-50 text-sky-700 ring-sky-200",
  extracted: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
};

export function Badge({ value, kind = "status" }) {
  const styles = kind === "severity" ? SEVERITY_STYLES : STATUS_STYLES;
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${styles[value] || "bg-slate-50 text-slate-600 ring-slate-200"}`}>
      {String(value).replaceAll("_", " ")}
    </span>
  );
}

export function ErrorText({ error }) {
  if (!error) return null;
  return <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>;
}

export function Notice({ children }) {
  return <p className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-500">{children}</p>;
}

// Small inline label for simulated / example content (MOCK, SYNTHETIC, ILLUSTRATIVE).
export function Tag({ children }) {
  return <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 ring-1 ring-inset ring-amber-200">{children}</span>;
}

export function Empty({ children }) {
  return <p className="py-6 text-center text-sm text-slate-400">{children}</p>;
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
    <form onSubmit={submit} className="flex w-full flex-col gap-2 rounded-md border border-slate-200 bg-slate-50 p-3">
      <label className="text-xs font-medium text-slate-600">{label}: reason</label>
      <textarea
        value={reason} onChange={(e) => setReason(e.target.value)} rows={2} minLength={5} required
        className="rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-brand-600 focus:outline-none"
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
  return new Date(value.endsWith("Z") ? value : `${value}Z`).toLocaleString(undefined, {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
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

// Standard table classes so every table looks the same.
export const table = {
  wrap: "overflow-x-auto",
  table: "w-full text-sm",
  head: "border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wide text-slate-500",
  th: "px-3 py-2",
  row: "border-b border-slate-100 last:border-0 hover:bg-slate-50",
  td: "px-3 py-2.5",
};
