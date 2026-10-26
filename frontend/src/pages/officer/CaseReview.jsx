import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import { DocumentPanel } from "../../components/Documents.jsx";
import { FindingsList, IncompleteChecks, SeveritySummary } from "../../components/Findings.jsx";
import Layout from "../../components/Layout.jsx";
import { PriorityPanel, VerificationPanel } from "../../components/ReviewTools.jsx";
import { Badge, Button, Card, ErrorText, Notice, ReasonForm, formatDate, useAsync } from "../../components/ui.jsx";

function InstituteRecord({ inst }) {
  const rows = [
    ["Reference", inst.aicte_ref], ["Address", inst.address], ["Approved intake", inst.approved_intake],
    ["Faculty on record", inst.faculty_count], ["Prior EoA", inst.prior_eoa_year],
    ["Deficiency status", inst.deficiency_status], ["TER payment", inst.ter_payment_status],
  ];
  return (
    <dl className="grid grid-cols-[9rem_1fr] gap-1 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="contents"><dt className="text-slate-500">{k}</dt><dd>{v ?? "-"}</dd></div>
      ))}
      {inst.is_synthetic && <dd className="col-span-2 mt-1 text-xs text-amber-700">SYNTHETIC mock institute record</dd>}
    </dl>
  );
}

function Decisions({ app, role, onDone }) {
  async function decide(decision, reason) {
    await api(`/applications/${app.id}/decision`, { method: "POST", body: { decision, reason } });
    onDone();
  }
  const officerCan = role === "scrutiny_officer" && app.status === "under_scrutiny";
  const seniorCan = role === "senior_authority" && ["under_scrutiny", "escalated"].includes(app.status);
  if (!officerCan && !seniorCan) return <p className="text-sm text-slate-500">No decision available in the current status.</p>;
  return (
    <div className="flex flex-col gap-2">
      <ReasonForm label="Mark scrutiny complete" onSubmit={(r) => decide("mark_scrutiny_complete", r)} />
      <ReasonForm label="Return for correction" variant="secondary" onSubmit={(r) => decide("return_for_correction", r)} />
      {officerCan && <ReasonForm label="Escalate" variant="warn" onSubmit={(r) => decide("escalate", r)} />}
      <p className="text-xs text-slate-500">Open critical/high findings must be resolved, dismissed or escalated before marking scrutiny complete.</p>
    </div>
  );
}

function AuditTrail({ appId, refreshKey }) {
  const [events, setEvents] = useState([]);
  useEffect(() => {
    api(`/audit?target_id=${appId}&limit=50`).then(setEvents).catch(() => setEvents([]));
  }, [appId, refreshKey]);
  return (
    <ul className="space-y-1 text-sm">
      {events.map((e) => (
        <li key={e.id} className="flex gap-2">
          <span className="text-xs text-slate-500">{formatDate(e.timestamp)}</span>
          <span className="font-mono text-xs">{e.event_type}</span>
          {e.payload?.reason && <span className="text-slate-600">"{e.payload.reason}"</span>}
        </li>
      ))}
      {events.length === 0 && <li className="text-slate-500">No events.</li>}
    </ul>
  );
}

export default function CaseReview({ basePath }) {
  const { id } = useParams();
  const { user } = useAuth();
  const [report, setReport] = useState(null);
  const [tick, setTick] = useState(0);
  const { busy, error, setError, run } = useAsync();

  const load = useCallback(() => {
    api(`/applications/${id}/report`).then(setReport).catch((e) => setError(e.message));
    setTick((t) => t + 1);
  }, [id, setError]);

  useEffect(load, [load]);

  if (!report) return <Layout><ErrorText error={error} />{!error && <p className="text-slate-500">Loading...</p>}</Layout>;

  const { application: app, institution: inst, run: lastRun } = report;
  const reviewing = ["under_scrutiny", "escalated"].includes(app.status);
  const canRevalidate = ["submitted", "under_scrutiny", "escalated"].includes(app.status);

  return (
    <Layout>
      <div className="flex flex-wrap items-center gap-3">
        <Link to={basePath} className="text-sm text-sky-700 hover:underline">&larr; Queue</Link>
        <h1 className="text-2xl font-semibold">{inst.name}</h1>
        <Badge value={app.status} />
        <span className="text-sm text-slate-500">{app.category.replaceAll("_", " ")} · v{app.current_version} · {app.academic_year}</span>
        <Link to={`/applications/${app.id}/report`} className="ml-auto text-sm text-sky-700 hover:underline">Printable report</Link>
      </div>
      <ErrorText error={error} />

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card
            title="Findings"
            actions={<>
              {app.status === "submitted" && (
                <Button disabled={busy} onClick={() => run(async () => { await api(`/applications/${app.id}/start-scrutiny`, { method: "POST" }); load(); })}>
                  Start scrutiny
                </Button>
              )}
              {canRevalidate && (
                <Button variant="secondary" disabled={busy} onClick={() => run(async () => { await api(`/applications/${app.id}/validate`, { method: "POST" }); load(); })}>
                  Re-run validation
                </Button>
              )}
            </>}
          >
            {lastRun ? (
              <div className="space-y-3">
                <p className="text-xs text-slate-500">
                  Run {lastRun.id.slice(0, 8)} · {formatDate(lastRun.started_at)} · rules {lastRun.rule_set_version} · checklist {lastRun.checklist_version} · application v{lastRun.application_version}
                </p>
                <SeveritySummary summary={report.summary} />
                <IncompleteChecks items={report.incomplete_checks} />
                {app.status === "submitted" && <Notice>Start scrutiny to review findings.</Notice>}
                <FindingsList findings={report.findings} documents={report.documents} rules={report.rules} canReview={reviewing} onChanged={load} />
              </div>
            ) : <p className="text-sm text-slate-500">No validation run yet.</p>}
          </Card>

          <Card title="Issuer verification: submitted value vs source value">
            <VerificationPanel verifications={report.verifications} canVerify={canRevalidate && user.role !== "admin"} onChanged={load} />
          </Card>

          <Card title="Documents and extracted values">
            <div className="grid gap-3">
              {report.documents.map((d) => <DocumentPanel key={d.id} doc={d} canCorrect={reviewing} onChanged={load} />)}
              {report.documents.length === 0 && <p className="text-sm text-slate-500">No documents uploaded.</p>}
            </div>
            {reviewing && <p className="mt-2 text-xs text-slate-500">Corrections are audited. Re-run validation afterwards to re-check.</p>}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Decision"><Decisions app={app} role={user.role} onDone={load} /></Card>
          <Card title="Review priority (aid only)"><PriorityPanel priority={report.priority} /></Card>
          <Card title="Institute record"><InstituteRecord inst={inst} /></Card>
          <Card title="Checklist">
            <ul className="space-y-1 text-sm">
              {report.checklist.map((c) => (
                <li key={c.doc_type} className="flex justify-between gap-2">
                  <span>{c.label}</span>
                  <span>{c.uploaded ? <Badge value={c.document_status} /> : <span className={`text-xs ${c.requirement === "required" ? "text-red-700" : "text-slate-400"}`}>{c.requirement === "required" ? "missing (required)" : "optional, not uploaded"}</span>}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="Audit trail (this application)"><AuditTrail appId={app.id} refreshKey={tick} /></Card>
        </div>
      </div>
    </Layout>
  );
}
