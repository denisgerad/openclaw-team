/**
 * openclaw/frontend/src/api.js
 * Typed API client wrapping fetch.
 * Token stored in localStorage; auto-attached to every request.
 */

const BASE = "/api";

function token() {
  return localStorage.getItem("oc_token");
}

async function req(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (token()) headers["Authorization"] = `Bearer ${token()}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  if (res.status === 204) return null;
  return res.json();
}

const get  = (path)        => req("GET",    path);
const post = (path, body)  => req("POST",   path, body);
const put  = (path, body)  => req("PUT",    path, body);
const del  = (path)        => req("DELETE", path);

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login    = (email, password) =>
  post("/auth/login", new URLSearchParams({ username: email, password }));  // form encoded
export const register = (data) => post("/auth/register", data);
export const getMe    = ()     => get("/auth/me");

// Override login for form-encoded (OAuth2PasswordRequestForm)
export async function loginUser(email, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(err.detail);
  }
  return res.json();
}

// ── Status ────────────────────────────────────────────────────────────────────
export const getTeamStatus    = ()          => get("/status/team");
export const getMemberHistory = (userId)    => get(`/status/member/${userId}`);
export const postStatus       = (data)      => post("/status/update", data);

// ── Engine ────────────────────────────────────────────────────────────────────
export const getEngineStatus  = ()          => get("/engine/status");
export const triggerWorker    = (name)      => post(`/engine/trigger/${name}`);
export const listWorkers      = ()          => get("/engine/workers");

// ── Notes ─────────────────────────────────────────────────────────────────────
export const getNotes         = ()          => get("/notes");
export const createNote       = (data)      => post("/notes", data);
export const updateNote       = (id, data)  => put(`/notes/${id}`, data);
export const deleteNote       = (id)        => del(`/notes/${id}`);

// ── Files ─────────────────────────────────────────────────────────────────────
export const getFiles         = ()          => get("/files");
export const queueDownload    = (data)      => post("/files/download", data);

// ── Sprint ────────────────────────────────────────────────────────────────────
export const getActiveSprint    = ()             => get("/sprint/active");
export const getSprintTasks     = ()             => get("/sprint/tasks");
export const createSprintTask   = (data)         => post("/sprint/tasks", data);
export const updateSprintTask   = (id, data)     => put(`/sprint/tasks/${id}`, data);
export const deleteSprintTask   = (id)           => del(`/sprint/tasks/${id}`);

// ── Documents ─────────────────────────────────────────────────────────────────
export const getDocuments     = (category) =>
  get(`/docs${category ? `?category=${encodeURIComponent(category)}` : ""}`);
export const getDocument      = (docId)        => get(`/docs/${docId}`);
export const getCategories    = ()             => get("/docs/categories");
export const updateDocMeta    = (docId, data)  => req("PATCH", `/docs/${docId}`, data);
export const deleteDocument   = (docId)        => del(`/docs/${docId}`);
export const deleteDocVersion = (docId, v)     => del(`/docs/${docId}/versions/${v}`);

export async function uploadDocument(formData) {
  const tok = localStorage.getItem("oc_token");
  const res = await fetch("/api/docs/upload", {
    method: "POST",
    headers: { Authorization: `Bearer ${tok}` },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function downloadDocVersion(docId, versionNum, filename) {
  const tok = localStorage.getItem("oc_token");
  const res = await fetch(`/api/docs/${docId}/versions/${versionNum}/download`, {
    headers: { Authorization: `Bearer ${tok}` },
  });
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
