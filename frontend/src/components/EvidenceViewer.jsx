import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { ErrorText } from "./ui.jsx";

// Shows one page of the original document with the evidence bbox highlighted.
// bbox is in PDF points (or image pixels); the page PNG is rendered at `page_scale` pixels per unit.
export default function EvidenceViewer({ documentId, page = 1, bbox }) {
  const [link, setLink] = useState(null);
  const [natural, setNatural] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setLink(null);
    setNatural(null);
    api(`/documents/${documentId}/link`, { method: "POST" }).then(setLink).catch((e) => setError(e.message));
  }, [documentId]);

  if (error) return <ErrorText error={error} />;
  if (!link) return <p className="text-sm text-slate-500">Loading page...</p>;

  const src = link.page_url_template.replace("{page}", String(page || 1));
  const box = bbox && natural && {
    left: `${((bbox[0] * link.page_scale) / natural.w) * 100}%`,
    top: `${((bbox[1] * link.page_scale) / natural.h) * 100}%`,
    width: `${(((bbox[2] - bbox[0]) * link.page_scale) / natural.w) * 100}%`,
    height: `${(((bbox[3] - bbox[1]) * link.page_scale) / natural.h) * 100}%`,
  };

  return (
    <div>
      <div className="relative overflow-hidden rounded border border-slate-300 bg-white">
        <img
          src={src} alt={`Page ${page} of the uploaded document`} className="block w-full"
          onLoad={(e) => setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
        />
        {box && (
          <div
            className="pointer-events-none absolute rounded-sm border-2 border-red-600 bg-yellow-300/30"
            style={{ ...box, margin: "-3px", padding: "3px", boxSizing: "content-box" }}
          />
        )}
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Page {page || 1}{bbox ? " · highlighted region from the extracted evidence" : " · no region recorded for this finding"} · link expires in {Math.round(link.expires_in_seconds / 60)} min
      </p>
    </div>
  );
}
