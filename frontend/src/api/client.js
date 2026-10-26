// Small fetch wrapper. All calls go to /api (proxied to the backend by Vite).
const TOKEN_KEY = "validex_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function errorMessage(data, res) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map((d) => d.msg).join("; ");
  return res.statusText || "Request failed";
}

export async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = form; // FormData: the browser sets the multipart boundary
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`/api${path}`, { method, headers, body: payload });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, errorMessage(data, res));
  return data;
}

// Ask the backend for a short-lived link and open the document in a new tab.
// The tab is opened before the await so popup blockers treat it as a user click.
export async function openDocument(documentId) {
  const tab = window.open("about:blank", "_blank");
  try {
    const { url } = await api(`/documents/${documentId}/link`, { method: "POST" });
    if (tab) tab.location.href = url;
  } catch (err) {
    tab?.close();
    throw err;
  }
}
