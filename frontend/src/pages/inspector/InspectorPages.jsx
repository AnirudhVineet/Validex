import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import { InspectionPanel } from "../../components/CaseTools.jsx";
import { FindingsList } from "../../components/Findings.jsx";
import Layout, { PageHeader } from "../../components/Layout.jsx";
import { Badge, Card, ErrorText, formatDate } from "../../components/ui.jsx";

// Minimal inspector view: flagged (escalated) cases only, enforced by the backend.
export function InspectorHome() {
  const [apps, setApps] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/applications").then(setApps).catch((e) => setError(e.message)); }, []);
  return (
    <Layout>
      <PageHeader title="Flagged cases" subtitle="Escalated applications that may need a site inspection." />
      <ErrorText error={error} />
      <Card>
        {!apps && <p className="text-sm text-slate-500">Loading...</p>}
        {apps?.length === 0 && <p className="text-sm text-slate-500">No flagged cases.</p>}
        {apps?.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500"><tr><th className="py-1">Institution</th><th>Status</th><th>Submitted</th><th /></tr></thead>
            <tbody>
              {apps.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  <td className="py-2">{a.institution_name}</td><td><Badge value={a.status} /></td>
                  <td>{formatDate(a.submitted_at)}</td>
                  <td className="text-right"><Link className="text-sky-700 hover:underline" to={`/inspector/applications/${a.id}`}>Open</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </Layout>
  );
}

export function InspectorCase() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api(`/applications/${id}/report`).then(setReport).catch((e) => setError(e.message)); }, [id]);
  if (!report) return <Layout><ErrorText error={error} />{!error && <p className="text-slate-500">Loading...</p>}</Layout>;
  return (
    <Layout>
      <PageHeader
        back={<Link to="/inspector" className="text-sm text-brand-700 hover:underline">&larr; Flagged cases</Link>}
        title={report.institution.name.replace("SYNTHETIC ", "")}
        subtitle={<Badge value={report.application.status} />}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Inspection notes and evidence"><InspectionPanel app={report.application} canAdd /></Card>
        <Card title="Findings">
          <FindingsList findings={report.findings} documents={report.documents} rules={report.rules} />
        </Card>
      </div>
    </Layout>
  );
}
