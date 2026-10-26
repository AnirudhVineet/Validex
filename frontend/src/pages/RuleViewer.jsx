import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import Layout from "../components/Layout.jsx";
import { Card, ErrorText, Notice } from "../components/ui.jsx";

// Scrutiny officers can read the active rules but cannot edit them (backend enforces this).
export default function RuleViewer() {
  const [rules, setRules] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/rules").then(setRules).catch((e) => setError(e.message)); }, []);
  return (
    <Layout>
      <h1 className="text-2xl font-semibold">Active validation rules</h1>
      <div className="mt-2"><Notice>Read-only. Rule changes are made by an admin or senior authority and are versioned and audited. Rules are ILLUSTRATIVE.</Notice></div>
      <ErrorText error={error} />
      {rules && (
        <Card title={`${rules.name} v${rules.version}`} className="mt-4">
          <pre className="max-h-[40rem] overflow-auto whitespace-pre-wrap text-xs">{rules.content_yaml}</pre>
        </Card>
      )}
    </Layout>
  );
}
