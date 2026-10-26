import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import Layout from "../../components/Layout.jsx";
import { Badge, Button, Card, ErrorText, formatDate, useAsync } from "../../components/ui.jsx";

export default function AdminHome() {
  const [events, setEvents] = useState([]);
  const [users, setUsers] = useState([]);
  const [verify, setVerify] = useState(null);
  const { busy, error, run } = useAsync();

  useEffect(() => {
    run(async () => {
      setEvents(await api("/audit?limit=200"));
      setUsers(await api("/users"));
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Layout>
      <h1 className="text-2xl font-semibold">Admin</h1>
      <ErrorText error={error} />

      <Card
        title="Audit log (hash-chained, tamper-evident)"
        className="mt-4"
        actions={<Button disabled={busy} onClick={() => run(async () => setVerify(await api("/audit/verify")))}>Verify chain</Button>}
      >
        {verify && (
          <p className={`mb-3 rounded px-3 py-2 text-sm ${verify.valid ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>
            {verify.valid
              ? `Chain intact: ${verify.events_checked} events verified.`
              : `Chain broken at event ${verify.first_bad_event_id}: ${verify.reason}`}
          </p>
        )}
        <div className="max-h-[32rem] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white text-left text-slate-500">
              <tr><th className="py-1">#</th><th>Time</th><th>Event</th><th>Target</th><th>Actor</th><th>Hash</th></tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-t border-slate-100">
                  <td className="py-1">{e.id}</td>
                  <td className="whitespace-nowrap text-xs">{formatDate(e.timestamp)}</td>
                  <td className="font-mono text-xs">{e.event_type}</td>
                  <td className="text-xs">{e.target_type} {e.target_id.slice(0, 8)}</td>
                  <td className="text-xs">{e.actor.slice(0, 8)}</td>
                  <td className="font-mono text-xs text-slate-500">{e.hash.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Users" className="mt-4">
        <table className="w-full text-sm">
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-slate-100">
                <td className="py-1">{u.name}</td><td>{u.email}</td><td><Badge value={u.role} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-slate-500">Rules are edited on the Rule editor page (admin and senior authority only).</p>
      </Card>
    </Layout>
  );
}
