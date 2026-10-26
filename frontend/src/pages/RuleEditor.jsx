import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import Layout, { PageHeader } from "../components/Layout.jsx";
import { Badge, Button, Card, ErrorText, Tag, formatDate, useAsync } from "../components/ui.jsx";

// Admin / senior authority only (enforced by the backend). Saving creates a new version;
// re-running validation keeps all earlier runs and findings for audit.
export default function RuleEditor() {
  const [active, setActive] = useState(null);
  const [versions, setVersions] = useState([]);
  const [text, setText] = useState("");
  const [reason, setReason] = useState("");
  const [check, setCheck] = useState(null);
  const [message, setMessage] = useState("");
  const { busy, error, run } = useAsync();

  async function load() {
    const current = await api("/rules");
    setActive(current);
    setText(current.content_yaml);
    setVersions(await api("/rules/versions"));
  }

  useEffect(() => { run(load); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const validate = () => run(async () => {
    setMessage("");
    setCheck(await api("/rules/validate", { method: "POST", body: { content_yaml: text } }));
  });

  const save = () => run(async () => {
    const saved = await api("/rules", { method: "PUT", body: { content_yaml: text, reason } });
    setMessage(`Saved as version ${saved.version}. Open cases still use their earlier runs until you re-run validation.`);
    setReason("");
    setCheck(null);
    await load();
  });

  const rerun = () => run(async () => {
    const res = await api("/rules/rerun", { method: "POST" });
    setMessage(`Re-ran official validation on ${res.applications_rerun} open case(s) with ${res.rule_set_version}. Earlier runs are kept.`);
  });

  return (
    <Layout>
      <PageHeader title="Validation rules" subtitle={<><Tag>Illustrative</Tag> Versioned and audited. Every rule is deterministic.</>} />
      <ErrorText error={error} />
      {message && <p className="mt-2 rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{message}</p>}

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title={active ? `Editing ${active.name} (active: v${active.version})` : "Loading..."} className="lg:col-span-2">
          <textarea
            value={text} onChange={(e) => { setText(e.target.value); setCheck(null); }} spellCheck={false}
            className="h-[34rem] w-full rounded border border-slate-300 p-2 font-mono text-xs"
          />
          {check && (
            check.valid
              ? <p className="mt-2 text-sm text-emerald-700">Valid: {check.rule_count} rules.</p>
              : <ul className="mt-2 list-disc pl-5 text-sm text-red-700">{check.errors.map((e) => <li key={e}>{e}</li>)}</ul>
          )}
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <Button variant="secondary" onClick={validate} disabled={busy}>Validate</Button>
            <label className="flex-1 text-sm">
              Reason for change (required, audited)
              <input value={reason} onChange={(e) => setReason(e.target.value)} className="mt-1 w-full rounded border px-2 py-1.5" />
            </label>
            <Button onClick={save} disabled={busy || !check?.valid || reason.trim().length < 5}>Save as new version</Button>
          </div>
          <p className="mt-2 text-xs text-slate-500">Validate first. The version number is set automatically on save.</p>
        </Card>

        <div className="space-y-4">
          <Card title="Re-run validation">
            <p className="text-sm text-slate-600">Run the active rules on every submitted, under-scrutiny and escalated case. Old runs and findings stay unchanged for audit.</p>
            <Button className="mt-3" variant="warn" onClick={rerun} disabled={busy}>Re-run on open cases</Button>
          </Card>
          <Card title="Versions">
            <ul className="space-y-1 text-sm">
              {versions.map((v) => (
                <li key={v.id} className="flex items-center justify-between gap-2">
                  <span>v{v.version} {v.is_active && <Badge value="active" />}</span>
                  <span className="text-xs text-slate-500">{formatDate(v.created_at)} · {v.content_hash.slice(0, 8)}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </Layout>
  );
}
