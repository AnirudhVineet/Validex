import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import { DocumentPanel } from "../../components/Documents.jsx";
import { FindingsList, IncompleteChecks, SeveritySummary } from "../../components/Findings.jsx";
import Layout from "../../components/Layout.jsx";
import { Badge, Button, Card, ErrorText, Notice, formatDate, useAsync } from "../../components/ui.jsx";

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
    <tr className="border-t border-slate-100 align-top">
      <td className="py-2 pr-3">
        <div className="font-medium">{item.label}</div>
        <div className="text-xs text-slate-500">{item.description}</div>
      </td>
      <td className="py-2 pr-3">
        <Badge value={item.requirement} />
        {item.configured_as === "conditional" && <div className="mt-1 text-xs text-slate-500">{item.reason}</div>}
      </td>
      <td className="py-2 pr-3">{item.uploaded ? <Badge value={item.document_status} /> : <span className="text-xs text-slate-400">not uploaded</span>}</td>
      <td className="py-2 text-right">
        {editable && (
          <label className="cursor-pointer rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100">
            {busy ? "Uploading..." : item.uploaded ? "Replace" : "Upload"}
            <input type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={onFile} disabled={busy} />
          </label>
        )}
        <ErrorText error={error} />
      </td>
    </tr>
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
    <form onSubmit={save} className="flex items-end gap-2">
      <label className="text-sm">
        Requested total intake
        <input type="number" min="0" required value={value} onChange={(e) => setValue(e.target.value)} className="mt-1 block rounded border px-2 py-1" />
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

  if (!report) return <Layout><ErrorText error={error} />{!error && <p className="text-slate-500">Loading...</p>}</Layout>;

  const { application: app, checklist, run: lastRun } = report;
  const editable = EDITABLE.includes(app.status);
  const missingRequired = checklist.filter((c) => c.requirement === "required" && !c.uploaded);

  return (
    <Layout>
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/applicant" className="text-sm text-sky-700 hover:underline">&larr; My applications</Link>
        <h1 className="text-2xl font-semibold">{report.institution.name}</h1>
        <Badge value={app.status} />
        <span className="text-sm text-slate-500">version {app.current_version} · {app.academic_year}</span>
        <Link to={`/applications/${app.id}/report`} className="ml-auto text-sm text-sky-700 hover:underline">Printable report</Link>
      </div>
      {app.status === "returned_for_correction" && (
        <p className="mt-3 rounded bg-amber-50 px-3 py-2 text-sm text-amber-900">
          This application was returned for correction. Replace the documents mentioned in the findings, run a pre-check, then resubmit.
        </p>
      )}
      <ErrorText error={error} />

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Checklist (illustrative)">
          {app.category === "eoa_increase_intake" && editable && <div className="mb-3"><IntakeForm app={app} onSaved={load} /></div>}
          <table className="w-full text-sm">
            <tbody>
              {checklist.map((item) => (
                <UploadSlot key={item.doc_type} item={item} appId={app.id} editable={editable} onUploaded={load} />
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-slate-500">PDF, PNG or JPEG, up to 10 MB. Files are checked by content, not by name.</p>
        </Card>

        <Card
          title="Pre-check results"
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
            <div className="space-y-3">
              <p className="text-xs text-slate-500">
                {lastRun.is_precheck ? "Pre-check" : "Official validation"} · {formatDate(lastRun.started_at)} · rules {lastRun.rule_set_version}
              </p>
              <SeveritySummary summary={report.summary} />
              <IncompleteChecks items={report.incomplete_checks} />
              <FindingsList findings={report.findings} documents={report.documents} rules={report.rules} />
            </div>
          ) : (
            <p className="text-sm text-slate-500">Run a pre-check to see what the automated checks find before you submit.</p>
          )}
        </Card>
      </div>

      {report.documents.length > 0 && (
        <Card title="Uploaded documents and extracted values" className="mt-4">
          <div className="grid gap-3 lg:grid-cols-2">
            {report.documents.map((d) => <DocumentPanel key={d.id} doc={d} canCorrect={false} />)}
          </div>
        </Card>
      )}

      {editable && (
        <Card title={app.status === "draft" ? "Submit" : "Resubmit"} className="mt-4">
          {missingRequired.length > 0 && (
            <p className="mb-2 text-sm text-amber-800">Still missing: {missingRequired.map((m) => m.label).join(", ")}. You can submit, but the officer will see these as findings.</p>
          )}
          {report.missing_form_fields.length > 0 && (
            <p className="mb-2 text-sm text-red-700">Fill in: {report.missing_form_fields.join(", ")}</p>
          )}
          <Notice>Submitting runs the official automated validation. An authorised official reviews the results and makes every decision.</Notice>
          <div className="mt-3">
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
