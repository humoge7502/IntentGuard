/* API client. Key lives in sessionStorage (per-tab); every request is
   org-scoped server-side by the key itself. */

const KEY_STORAGE = "ig_key";

export function getKey() {
  return sessionStorage.getItem(KEY_STORAGE) || "";
}

export function setKey(key) {
  if (key) sessionStorage.setItem(KEY_STORAGE, key);
  else sessionStorage.removeItem(KEY_STORAGE);
}

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message || code);
    this.status = status;
    this.code = code;
  }
}

async function request(method, path, body) {
  const headers = { Accept: "application/json" };
  const key = getKey();
  if (key) headers["X-API-Key"] = key;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new ApiError(0, "NETWORK", "cannot reach the IntentGuard API — is the server running?");
  }
  if (response.status === 403) {
    setKey("");
    throw new ApiError(403, "AUTH", "invalid, revoked, or missing API key");
  }
  if (!response.ok) {
    let code = "ERROR", message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      code = data.error || code;
      message = data.message || message;
    } catch { /* non-JSON error body */ }
    throw new ApiError(response.status, code, message);
  }
  return response.json();
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body ?? {}),
};

/* Server-sent events stream for live firewall decisions. */
export function openEventStream(onEvent, onStatus) {
  const key = getKey();
  const source = new EventSource(`/api/v1/events/stream${key ? `?api_key=${encodeURIComponent(key)}` : ""}`);
  source.onopen = () => onStatus?.("live");
  source.onerror = () => onStatus?.("error");
  source.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data));
    } catch { /* ignore malformed frames */ }
  };
  return () => source.close();
}
