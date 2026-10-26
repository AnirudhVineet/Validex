import { api } from "../api/client.js";
import { Badge, ReasonForm } from "./ui.jsx";

const REVIEW_ACTIONS = [
  { action: "resolve", label: "Resolve", variant: "primary" },
  { action: "dismiss", label: "Dismiss", variant: "secondary" },
  { action: "escalate", label: "Escalate", variant: "warn" },
];

function Row({ label, children }) {
  if (children === null || children === undefined || children === "") return null;
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-2 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  );
}

function evidenceText(evidence) {
  if (!evidence) return null;
  const parts = [];
  if (evidence.page) parts.push(`page ${evidence.page}`);
  if (evidence.bbox) parts.push(`region [${evidence.bbox.map((n) => Math.round(n)).join(", ")}]`);
  if (evidence.snippet) parts.push(`"${evidence.snippet}"`);
  return parts.join(" · ");
}

export function FindingCard({ finding, docLabel, canReview, onChanged }) {
  async function review(action, reason) {
    await api(`/findings/${finding.id}/review`, { method: "POST", body: { action, reason } });
    onChanged?.();
  }
  const reviewable = canReview && finding.status === "open";

  return (
    <article className="rounded border border-slate-200 p-3">
      <header className="flex flex-wrap items-center gap-2">
        <Badge value={finding.severity} kind="severity" />
        <span className="font-medium">{finding.title}</span>
        <span className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          {finding.rule_id} v{finding.rule_version} <Badge value={finding.status} />
        </span>
      </header>
      <dl className="mt-2 space-y-1">
        <Row label="Document">{docLabel}</Row>
        <Row label="Found">{finding.found_value}</Row>
        <Row label="Expected">{finding.expected_value}</Row>
        <Row label="Evidence">{evidenceText(finding.evidence)}</Row>
        <Row label="Why">{finding.explanation}</Row>
        <Row label="Suggested action">{finding.suggested_action}</Row>
        <Row label="Review note">{finding.review_reason}</Row>
      </dl>
      {reviewable && (
        <div className="mt-3 flex flex-wrap gap-2">
          {REVIEW_ACTIONS.map((a) => (
            <ReasonForm key={a.action} label={a.label} variant={a.variant} onSubmit={(r) => review(a.action, r)} />
          ))}
        </div>
      )}
    </article>
  );
}

export function FindingsList({ findings, documents, canReview, onChanged }) {
  const labels = Object.fromEntries((documents || []).map((d) => [d.id, d.doc_type.replaceAll("_", " ")]));
  if (!findings.length) return <p className="text-sm text-slate-500">No findings in this run.</p>;
  return (
    <div className="space-y-3">
      {findings.map((f) => (
        <FindingCard key={f.id} finding={f} docLabel={labels[f.document_id]} canReview={canReview} onChanged={onChanged} />
      ))}
    </div>
  );
}

export function IncompleteChecks({ items }) {
  if (!items?.length) return null;
  // Group by document + reason so a failed document shows once.
  const groups = {};
  for (const item of items) {
    const key = `${item.doc_type || "general"}|${item.reason}`;
    groups[key] = groups[key] || { ...item, rules: [] };
    groups[key].rules.push(item.rule_id);
  }
  return (
    <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm">
      <p className="font-medium text-amber-900">Checks that could not complete (need manual review)</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-amber-900">
        {Object.values(groups).map((g) => (
          <li key={`${g.doc_type}${g.reason}`}>
            <span className="font-medium">{(g.doc_type || "general").replaceAll("_", " ")}</span>: {g.reason}{" "}
            <span className="text-xs text-amber-700">({[...new Set(g.rules)].join(", ")})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SeveritySummary({ summary }) {
  return (
    <div className="flex flex-wrap gap-2">
      {Object.entries(summary || {}).map(([severity, count]) => (
        <span key={severity} className="flex items-center gap-1 text-sm">
          <Badge value={severity} kind="severity" /> {count}
        </span>
      ))}
    </div>
  );
}
