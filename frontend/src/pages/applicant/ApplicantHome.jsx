import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client.js";
import Layout from "../../components/Layout.jsx";
import { AlertsPanel } from "../../components/ReviewTools.jsx";
import { Badge, Button, Card, ErrorText, Notice, formatDate } from "../../components/ui.jsx";

const CATEGORIES = [
  { value: "eoa_no_change", label: "Extension of Approval: no change" },
  { value: "eoa_increase_intake", label: "Extension of Approval: increase in intake" },
];

function NewApplication({ onCreated }) {
  const [category, setCategory] = useState(CATEGORIES[0].value);
  const [year, setYear] = useState("2027-28");
  const [intake, setIntake] = useState("");
  const [error, setError] = useState("");

  async function create(e) {
    e.preventDefault();
    setError("");
    const form_data = category === "eoa_increase_intake" && intake ? { requested_intake: Number(intake) } : {};
    try {
      onCreated(await api("/applications", { method: "POST", body: { category, academic_year: year, form_data } }));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={create} className="grid gap-3 sm:grid-cols-4 sm:items-end">
      <label className="text-sm sm:col-span-2">
        Category
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="mt-1 w-full rounded border px-2 py-1.5">
          {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </label>
      <label className="text-sm">
        Academic year
        <input value={year} onChange={(e) => setYear(e.target.value)} pattern="[0-9]{4}-[0-9]{2}" className="mt-1 w-full rounded border px-2 py-1.5" />
      </label>
      {category === "eoa_increase_intake" ? (
        <label className="text-sm">
          Requested total intake
          <input type="number" min="0" value={intake} onChange={(e) => setIntake(e.target.value)} className="mt-1 w-full rounded border px-2 py-1.5" />
        </label>
      ) : <div />}
      <div className="sm:col-span-4">
        <ErrorText error={error} />
        <Button type="submit">Start application</Button>
      </div>
    </form>
  );
}

export default function ApplicantHome() {
  const navigate = useNavigate();
  const [apps, setApps] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/applications").then(setApps).catch((e) => setError(e.message));
  }, []);

  return (
    <Layout>
      <h1 className="text-2xl font-semibold">My applications</h1>
      <p className="mt-1 text-slate-600">Upload documents, run a pre-check to catch problems early, then submit.</p>
      <div className="mt-4"><Notice>Checklists are ILLUSTRATIVE for this prototype and are not the official AICTE requirement list.</Notice></div>
      <ErrorText error={error} />

      <Card title="Alerts" className="mt-4"><AlertsPanel appBasePath="/applicant" /></Card>

      <Card title="Applications" className="mt-4">
        {!apps && <p className="text-sm text-slate-500">Loading...</p>}
        {apps?.length === 0 && <p className="text-sm text-slate-500">No applications yet. Start one below.</p>}
        {apps?.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr><th className="py-1">Category</th><th>Year</th><th>Status</th><th>Version</th><th>Updated</th><th /></tr>
            </thead>
            <tbody>
              {apps.map((a) => (
                <tr key={a.id} className="border-t border-slate-100">
                  <td className="py-2">{CATEGORIES.find((c) => c.value === a.category)?.label}</td>
                  <td>{a.academic_year}</td>
                  <td><Badge value={a.status} /></td>
                  <td>v{a.current_version}</td>
                  <td>{formatDate(a.updated_at)}</td>
                  <td className="text-right"><Link className="text-sky-700 hover:underline" to={`/applicant/applications/${a.id}`}>Open</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Start a new application" className="mt-4">
        <NewApplication onCreated={(a) => navigate(`/applicant/applications/${a.id}`)} />
      </Card>
    </Layout>
  );
}
