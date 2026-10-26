import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import { InspectionPanel, LetterPanel, SummaryPanel } from "../../components/CaseTools.jsx";
import { DocumentPanel } from "../../components/Documents.jsx";
import { FindingsList, IncompleteChecks, SeveritySummary } from "../../components/Findings.jsx";
import Layout, { PageHeader } from "../../components/Layout.jsx";
import { PriorityPanel, VerificationPanel } from "../../components/ReviewTools.jsx";
import { Badge, Button, Card, Empty, ErrorText, ReasonForm, Tag, formatDate, useAsync } from "../../components/ui.jsx";

function InstituteRecord({ inst }) {
  const rows = [
    ["Reference", inst.aicte_ref], ["Approved intake", inst.approved_intake], ["Faculty on record", inst.faculty_count],
    ["Prior EoA", inst.prior_eoa_year], ["Deficiency", inst.deficiency_status], ["TER payment", inst.ter_payment_status],
  ];
  return (
    <dl className="grid grid-cols-[8rem_1fr] gap-y-1.5 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="contents"><dt className="text-slate-500">{k}</dt><dd className="capitalize">{v ?? "-"}</dd></div>
      ))}
      <dt className="text-slate-500">Address</dt><dd>{inst.address}</dd>
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
  if (!officerCan && !seniorCan) return <p className="text-sm text-slate-500">No decision available at this stage.</p>;
  return (
    <div className="flex flex-col gap-2">
      <ReasonForm label="Mark scrutiny complete" onSubmit={(r) => decide("mark_scrutiny_complete", r)} />
      <ReasonForm label="Return for correction" variant="secondary" onSubmit={(r) => decide("return_for_correction", r)} />
      {officerCan && <ReasonForm label="Escalate" variant="warn" onSubmit={(r) => decide("escalate", r)} />}
      <p className="text-xs text-slate-400">Critical and high findings must be closed first.</p>
    </div>
  );
}

function AuditTrail({ appId, refreshKey }) {
  const [events, setEvents] = useState([]);
  useEffect(() => {
    api(`/audit?target_id=${appId}&limit=50`).then(setEvents).catch(() => setEvents([]));
  }, [appId, refreshKey]);
  if (!events.length) return <Empty>No events.</Empty>;
  return (
    <ol className="relative space-y-3 border-l border-slate-200 pl-4 text-sm">
      {events.map((e) => (
        <li key={e.id}>
          <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-brand-600" />
          <div className="font-medium text-slate-700">{e.event_type.replaceAll(".", " · ").replaceAll("_", " ")}</div>
          <div className="text-xs text-slate-400">{formatDate(e.timestamp)}</div>
          {e.payload?.reason && <div className="mt-0.5 text-slate-600">"{e.payload.reason}"</div>}
        </li>
      ))}
    </ol>
  );
}

const TABS = ["Findings", "Issuer verification", "Documents", "Inspection", "Audit trail"];

export default function CaseReview({ basePath }) {
  const { id } = useParams();
  const { user } = useAuth();
  const [report, setReport] = useState(null);
  const [tick, setTick] = useState(0);
  const [tab, setTab] = useState(TABS[0]);
  const { busy, error, setError, run } = useAsync();

  const load = useCallback(() => {
    api(`/applications/${id}/report`).then(setReport).catch((e) => setError(e.message));
    setTick((t) => t + 1);
  }, [id, setError]);

  useEffect(load, [load]);

  if (!report) return <Layout><ErrorText error={error} />{!error && <Empty>Loading...</Empty>}</Layout>;

  const { application: app, institution: inst, run: lastRun } = report;
  const reviewing = ["under_scrutiny", "escalated"].includes(app.status);
  const canRevalidate = ["submitted", "under_scrutiny", "escalated"].includes(app.status);
  const counts = { Findings: report.findings.filter((f) => f.status === "open").length, Documents: report.documents.length,
    "Issuer verification": report.verifications.length };

  return (
    <Layout>
      <PageHeader
        back={<Link to={basePath} className="text-sm text-brand-700 hover:underline">&larr; Queue</Link>}
        title={inst.name.replace("SYNTHETIC ", "")}
        subtitle={<>
          <Badge value={app.status} />
          <span>{app.category === "eoa_increase_intake" ? "Increase in intake" : "No change"} · v{app.current_version} · {app.academic_year}</span>
          {inst.is_synthetic && <Tag>Synthetic</Tag>}
        </>}
      >
        <Link to={`/applications/${app.id}/report`} className="text-sm font-medium text-brand-700 hover:underline">Printable report</Link>
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
      </PageHeader>
      <ErrorText error={error} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200">
            {TABS.map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === t ? "border-brand-700 font-medium text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
                {t}{counts[t] ? <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 text-xs text-slate-600">{counts[t]}</span> : null}
              </button>
            ))}
          </div>

          {tab === "Findings" && (
            <Card>
              {lastRun ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <SeveritySummary summary={report.summary} />
                    <span className="text-xs text-slate-400" title={`Run ${lastRun.id}`}>
                      {formatDate(lastRun.started_at)} · rules {lastRun.rule_set_version}
                    </span>
                  </div>
                  <IncompleteChecks items={report.incomplete_checks} />
                  {app.status === "submitted" && <p className="text-sm text-slate-500">Start scrutiny to review findings.</p>}
                  <FindingsList findings={report.findings} documents={report.documents} rules={report.rules} canReview={reviewing} onChanged={load} />
                </div>
              ) : <Empty>No validation run yet.</Empty>}
            </Card>
          )}
          {tab === "Issuer verification" && (
            <Card><VerificationPanel verifications={report.verifications} canVerify={canRevalidate && user.role !== "admin"} onChanged={load} /></Card>
          )}
          {tab === "Documents" && (
            <Card>
              <div className="grid gap-4">
                {report.documents.map((d) => <DocumentPanel key={d.id} doc={d} canCorrect={reviewing} onChanged={load} />)}
                {report.documents.length === 0 && <Empty>No documents uploaded.</Empty>}
              </div>
            </Card>
          )}
          {tab === "Inspection" && <Card><InspectionPanel app={app} canAdd={false} /></Card>}
          {tab === "Audit trail" && <Card><AuditTrail appId={app.id} refreshKey={tick} /></Card>}
        </div>

        <div className="space-y-6">
          <Card title="Decision"><Decisions app={app} role={user.role} onDone={load} /></Card>
          <Card title="Review priority"><PriorityPanel priority={report.priority} /></Card>
          <Card title="Institute record"><InstituteRecord inst={inst} /></Card>
          <Card title="Checklist">
            <ul className="space-y-2 text-sm">
              {report.checklist.map((c) => (
                <li key={c.doc_type} className="flex items-center justify-between gap-2">
                  <span className="text-slate-700">{c.label}</span>
                  {c.uploaded ? <Badge value={c.document_status} />
                    : <span className={`text-xs ${c.requirement === "required" ? "font-medium text-red-700" : "text-slate-400"}`}>{c.requirement === "required" ? "Missing" : "Optional"}</span>}
                </li>
              ))}
            </ul>
          </Card>
          {user.role !== "admin" && (
            <Card title="Deficiency letter">
              <LetterPanel app={app} onReturned={load}
                canReturn={(user.role === "scrutiny_officer" && app.status === "under_scrutiny") || (user.role === "senior_authority" && ["under_scrutiny", "escalated"].includes(app.status))} />
            </Card>
          )}
          <Card title="AI summary"><SummaryPanel app={app} findings={report.findings} /></Card>
        </div>
      </div>
    </Layout>
  );
}
