import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import Layout, { PageHeader } from "../components/Layout.jsx";
import { Card, ErrorText, Tag } from "../components/ui.jsx";

// Scrutiny officers can read the active rules but cannot edit them (backend enforces this).
export default function RuleViewer() {
  const [rules, setRules] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/rules").then(setRules).catch((e) => setError(e.message)); }, []);
  return (
    <Layout>
      <PageHeader title="Validation rules" subtitle={<><Tag>Illustrative</Tag> Read-only. Changed by admin or senior authority.</>} />
      <ErrorText error={error} />
      {rules && (
        <Card title={`${rules.name} v${rules.version}`} className="mt-4">
          <pre className="max-h-[40rem] overflow-auto whitespace-pre-wrap text-xs">{rules.content_yaml}</pre>
        </Card>
      )}
    </Layout>
  );
}
