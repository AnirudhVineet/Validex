import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client.js";
import { FindingsList, IncompleteChecks, SeveritySummary } from "../components/Findings.jsx";
import Layout from "../components/Layout.jsx";
import { Badge, Button, Card, ErrorText, formatDate } from "../components/ui.jsx";

// Structured, printable validation report. The backend filters it by role.
export default function ReportPage() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/applications/${id}/report`).then(setReport).catch((e) => setError(e.message));
  }, [id]);

  if (!report) return <Layout><ErrorText error={error} />{!error && <p className="text-slate-500">Loading...</p>}</Layout>;
  const { application: app, institution: inst, run } = report;

  return (
    <Layout>
      <div className="flex items-center gap-3 print:hidden">
        <Button variant="secondary" onClick={() => window.history.back()}>&larr; Back</Button>
        <Button variant="secondary" onClick={() => window.print()}>Print</Button>
      </div>
      <h1 className="mt-4 text-2xl font-semibold">Validation report</h1>
      <p className="text-sm text-slate-500">Decision support only. Rules are illustrative.</p>

      <Card title="Application" className="mt-4">
        <dl className="grid grid-cols-[10rem_1fr] gap-1 text-sm">
          <dt className="text-slate-500">Institution</dt><dd>{inst.name} ({inst.aicte_ref})</dd>
          <dt className="text-slate-500">Category</dt><dd>{app.category.replaceAll("_", " ")}</dd>
          <dt className="text-slate-500">Status</dt><dd><Badge value={app.status} /></dd>
          <dt className="text-slate-500">Version</dt><dd>v{app.current_version}</dd>
          {run && <>
            <dt className="text-slate-500">Run</dt>
            <dd>{run.is_precheck ? "Pre-check" : "Official"} · {formatDate(run.started_at)} · {run.id}</dd>
            <dt className="text-slate-500">Rule set / checklist</dt><dd>{run.rule_set_version} / {run.checklist_version} (illustrative)</dd>
          </>}
        </dl>
      </Card>

      <Card title="Checklist" className="mt-4">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500"><tr><th>Document</th><th>Requirement</th><th>Why</th><th>Uploaded</th></tr></thead>
          <tbody>
            {report.checklist.map((c) => (
              <tr key={c.doc_type} className="border-t border-slate-100">
                <td className="py-1">{c.label}</td><td>{c.requirement}</td><td className="text-slate-600">{c.reason}</td>
                <td>{c.uploaded ? c.document_status : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Findings" className="mt-4">
        {run ? (
          <div className="space-y-3">
            <SeveritySummary summary={report.summary} />
            <IncompleteChecks items={report.incomplete_checks} />
            <FindingsList findings={report.findings} documents={report.documents} rules={report.rules} />
          </div>
        ) : <p className="text-sm text-slate-500">No validation run yet.</p>}
      </Card>
    </Layout>
  );
}
