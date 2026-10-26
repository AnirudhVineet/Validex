import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import { DocumentPanel } from "../../components/Documents.jsx";
import { FindingsList, IncompleteChecks, SeveritySummary } from "../../components/Findings.jsx";
import Layout, { PageHeader } from "../../components/Layout.jsx";
import { Badge, Button, Card, Empty, ErrorText, Tag, formatDate, useAsync } from "../../components/ui.jsx";

const EDITABLE = ["draft", "returned_for_correction"];

function UploadSlot({ item, appId, editable, onUploaded }) {
  const { busy, error, run } = useAsync();

  async function onFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const form = new FormData();
    form.append("doc_type", item.doc_type);
    form.append("file", file);
    await run(async () => {
      await api(`/applications/${appId}/documents`, { method: "POST", form });
      onUploaded();
    });
  }

  return (
    <li className="flex items-start justify-between gap-3 py-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{item.label}</span>
          <Badge value={item.requirement} />
        </div>
        {item.configured_as === "conditional" && <div className="mt-1 text-xs text-slate-500">{item.reason}</div>}
        <ErrorText error={error} />
      </div>
      <div className="flex flex-none items-center gap-3">
        {item.uploaded ? <Badge value={item.document_status} /> : <span className="text-xs text-slate-400">Not uploaded</span>}
        {editable && (
          <label className="cursor-pointer rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">
            {busy ? "Uploading..." : item.uploaded ? "Replace" : "Upload"}
            <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={onFile} disabled={busy} />
          </label>
        )}
      </div>
    </li>
  );
}

function IntakeForm({ app, onSaved }) {
  const [value, setValue] = useState(app.form_data?.requested_intake ?? "");
  const { busy, error, run } = useAsync();
  async function save(e) {
    e.preventDefault();
    await run(async () => {
      await api(`/applications/${app.id}`, { method: "PATCH", body: { form_data: { requested_intake: Number(value) } } });
      onSaved();
    });
  }
  return (
    <form onSubmit={save} className="mb-2 flex items-end gap-2 border-b border-slate-100 pb-4">
      <label className="text-sm font-medium text-slate-700">
        Requested total intake
        <input type="number" min="0" required value={value} onChange={(e) => setValue(e.target.value)}
          className="mt-1 block rounded-md border border-slate-300 px-3 py-1.5" />
      </label>
      <Button type="submit" variant="secondary" disabled={busy}>Save</Button>
      <ErrorText error={error} />
    </form>
  );
}

export default function ApplicationWorkspace() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const { busy, error, setError, run } = useAsync();

  const load = useCallback(() => {
    api(`/applications/${id}/report`).then(setReport).catch((e) => setError(e.message));
  }, [id, setError]);

  useEffect(load, [load]);

  if (!report) return <Layout><ErrorText error={error} />{!error && <Empty>Loading...</Empty>}</Layout>;

  const { application: app, checklist, run: lastRun } = report;
  const editable = EDITABLE.includes(app.status);
  const missingRequired = checklist.filter((c) => c.requirement === "required" && !c.uploaded);

  return (
    <Layout>
      <PageHeader
        back={<Link to="/applicant" className="text-sm text-brand-700 hover:underline">&larr; Applications</Link>}
        title={report.institution.name}
        subtitle={<><Badge value={app.status} /> <span>Version {app.current_version} · {app.academic_year}</span></>}
      >
        <Link to={`/applications/${app.id}/report`} className="text-sm font-medium text-brand-700 hover:underline">Printable report</Link>
      </PageHeader>

      {app.status === "returned_for_correction" && (
        <p className="mb-6 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Returned for correction. Fix the items below, run a pre-check, then resubmit.
        </p>
      )}
      <ErrorText error={error} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Document checklist" actions={<Tag>Illustrative</Tag>}>
          {app.category === "eoa_increase_intake" && editable && <IntakeForm app={app} onSaved={load} />}
          <ul className="divide-y divide-slate-100">
            {checklist.map((item) => (
              <UploadSlot key={item.doc_type} item={item} appId={app.id} editable={editable} onUploaded={load} />
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-400">PDF, PNG or JPEG · max 10 MB</p>
        </Card>

        <Card
          title={editable ? "Pre-check" : "Check results"}
          actions={editable && (
            <Button variant="secondary" disabled={busy} onClick={() => run(async () => {
              await api(`/applications/${app.id}/validate?precheck=true`, { method: "POST" });
              load();
            })}>
              {busy ? "Checking..." : "Run pre-check"}
            </Button>
          )}
        >
          {lastRun ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <SeveritySummary summary={report.summary} />
                <span className="text-xs text-slate-400">{formatDate(lastRun.started_at)}</span>
              </div>
              <IncompleteChecks items={report.incomplete_checks} />
              <FindingsList findings={report.findings} documents={report.documents} rules={report.rules} />
            </div>
          ) : (
            <Empty>Run a pre-check to see issues before you submit.</Empty>
          )}
        </Card>
      </div>

      {report.documents.length > 0 && (
        <Card title="Uploaded documents" className="mt-6">
          <div className="grid gap-4 lg:grid-cols-2">
            {report.documents.map((d) => <DocumentPanel key={d.id} doc={d} canCorrect={false} />)}
          </div>
        </Card>
      )}

      {editable && (
        <Card title={app.status === "draft" ? "Submit" : "Resubmit"} className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-1 text-sm">
              {missingRequired.length > 0 && (
                <p className="text-amber-800">Missing: {missingRequired.map((m) => m.label).join(", ")}</p>
              )}
              {report.missing_form_fields.length > 0 && (
                <p className="text-red-700">Fill in: {report.missing_form_fields.join(", ")}</p>
              )}
              <p className="text-slate-500">An officer reviews every result after submission.</p>
            </div>
            <Button disabled={busy} onClick={() => run(async () => {
              await api(`/applications/${app.id}/submit`, { method: "POST" });
              load();
            })}>
              {app.status === "draft" ? "Submit application" : "Resubmit application"}
            </Button>
          </div>
        </Card>
      )}
    </Layout>
  );
}
