import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client.js";
import Layout, { PageHeader } from "../../components/Layout.jsx";
import { AlertsPanel } from "../../components/ReviewTools.jsx";
import { Badge, Button, Card, Empty, ErrorText, Tag, formatDate, table } from "../../components/ui.jsx";

const CATEGORIES = [
  { value: "eoa_no_change", label: "Extension of Approval - no change" },
  { value: "eoa_increase_intake", label: "Extension of Approval - increase in intake" },
];

function NewApplication({ onCreated }) {
  const [category, setCategory] = useState(CATEGORIES[0].value);
  const [year, setYear] = useState("2027-28");
  const [intake, setIntake] = useState("");
  const [error, setError] = useState("");
  const input = "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm";

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
    <form onSubmit={create} className="grid gap-4 sm:grid-cols-4 sm:items-end">
      <label className="text-sm font-medium text-slate-700 sm:col-span-2">
        Category
        <select value={category} onChange={(e) => setCategory(e.target.value)} className={input}>
          {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </label>
      <label className="text-sm font-medium text-slate-700">
        Academic year
        <input value={year} onChange={(e) => setYear(e.target.value)} pattern="[0-9]{4}-[0-9]{2}" className={input} />
      </label>
      {category === "eoa_increase_intake" ? (
        <label className="text-sm font-medium text-slate-700">
          Requested total intake
          <input type="number" min="0" value={intake} onChange={(e) => setIntake(e.target.value)} className={input} />
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
      <PageHeader title="Applications" subtitle="Prepare, check and submit Extension of Approval applications." />
      <ErrorText error={error} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="My applications">
            {!apps && <Empty>Loading...</Empty>}
            {apps?.length === 0 && <Empty>No applications yet.</Empty>}
            {apps?.length > 0 && (
              <div className={table.wrap}>
                <table className={table.table}>
                  <thead className={table.head}>
                    <tr><th className={table.th}>Category</th><th className={table.th}>Year</th><th className={table.th}>Status</th><th className={table.th}>Version</th><th className={table.th}>Updated</th><th /></tr>
                  </thead>
                  <tbody>
                    {apps.map((a) => (
                      <tr key={a.id} className={table.row}>
                        <td className={table.td}>{CATEGORIES.find((c) => c.value === a.category)?.label}</td>
                        <td className={table.td}>{a.academic_year}</td>
                        <td className={table.td}><Badge value={a.status} /></td>
                        <td className={table.td}>v{a.current_version}</td>
                        <td className={`${table.td} text-slate-500`}>{formatDate(a.updated_at)}</td>
                        <td className={`${table.td} text-right`}>
                          <Link className="font-medium text-brand-700 hover:underline" to={`/applicant/applications/${a.id}`}>Open</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title="New application" actions={<Tag>Illustrative checklists</Tag>}>
            <NewApplication onCreated={(a) => navigate(`/applicant/applications/${a.id}`)} />
          </Card>
        </div>

        <Card title="Alerts"><AlertsPanel appBasePath="/applicant" /></Card>
      </div>
    </Layout>
  );
}
