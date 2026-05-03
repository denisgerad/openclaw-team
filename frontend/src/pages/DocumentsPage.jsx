/**
 * openclaw/frontend/src/pages/DocumentsPage.jsx
 *
 * Document Management System — Step 1 UI
 *
 * Features:
 *  - Category sidebar filter (Requirements, Design, Review, etc.)
 *  - Document list with owner, version, size, date
 *  - Upload modal — new document or new version of existing
 *  - Version history drawer — per document, with download per version
 *  - Edit metadata (name, category, description, privacy)
 *  - Delete document or single version
 *  - Private badge on owner-only docs
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { T, Btn, Modal, Field, Input, Select, Textarea } from "../components/Sidebar";

// ── inline API calls (paste into api.js in production) ───────────────────────
function token() { return localStorage.getItem("oc_token"); }
const authHdr = () => ({ Authorization: `Bearer ${token()}` });

async function apiFetch(method, path, body) {
  const headers = { "Content-Type": "application/json", ...authHdr() };
  const res = await fetch(`/api${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail); }
  if (res.status === 204) return null;
  return res.json();
}
const apiGet   = p      => apiFetch("GET",    p);
const apiPatch = (p, b) => apiFetch("PATCH",  p, b);
const apiDel   = p      => apiFetch("DELETE", p);

async function apiUpload(formData) {
  const res = await fetch("/api/docs/upload", { method: "POST", headers: authHdr(), body: formData });
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail); }
  return res.json();
}

async function apiDownload(docId, versionNum, filename) {
  const res = await fetch(`/api/docs/${docId}/versions/${versionNum}/download`, { headers: authHdr() });
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ── Constants ─────────────────────────────────────────────────────────────────
const CATEGORIES = ["All", "Requirements", "Design", "Review", "Report", "Change Request", "Test Plan", "Architecture", "Meeting Notes", "Other"];

const CAT_COLORS = {
  Requirements:    "#7dd3fc",
  Design:          "#c4b5fd",
  Review:          "#86efac",
  Report:          "#fcd34d",
  "Change Request":"#f9a8d4",
  "Test Plan":     "#6ee7b7",
  Architecture:    "#93c5fd",
  "Meeting Notes": "#d9f99d",
  Other:           "#cbd5e1",
};

function fmt(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes/1024).toFixed(1)} KB`;
  return `${(bytes/1048576).toFixed(1)} MB`;
}
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", { hour12:false, day:"2-digit", month:"short", year:"numeric", hour:"2-digit", minute:"2-digit" });
}

// ── Category badge ────────────────────────────────────────────────────────────
function CatBadge({ cat }) {
  const color = CAT_COLORS[cat] || "#cbd5e1";
  return (
    <span style={{ fontFamily:T.mono, fontSize:9, padding:"2px 7px", borderRadius:2, background:color+"22", border:`1px solid ${color}55`, color, whiteSpace:"nowrap" }}>
      {cat}
    </span>
  );
}

// ── Upload Modal ──────────────────────────────────────────────────────────────
function UploadModal({ existingDoc, onDone, onClose }) {
  const fileRef = useRef();
  const [form, setForm] = useState({
    name:        existingDoc?.name || "",
    category:    existingDoc?.category || "Requirements",
    description: existingDoc?.description || "",
    change_note: existingDoc ? "Updated version" : "Initial upload",
    is_private:  existingDoc?.is_private || false,
  });
  const [file, setFile]     = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState(null);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  async function handleUpload() {
    if (!file)        { setError("Please select a file"); return; }
    if (!form.name)   { setError("Document name is required"); return; }

    setSaving(true); setError(null);
    try {
      const fd = new FormData();
      fd.append("file",        file);
      fd.append("name",        form.name);
      fd.append("category",    form.category);
      fd.append("description", form.description);
      fd.append("change_note", form.change_note);
      fd.append("is_private",  String(form.is_private));
      if (existingDoc) fd.append("doc_id", String(existingDoc.id));

      await apiUpload(fd);
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={existingDoc ? `New Version // ${existingDoc.name}` : "Upload Document"}
      onClose={onClose}
      footer={<>
        <Btn variant="ghost" onClick={onClose}>Cancel</Btn>
        <Btn onClick={handleUpload} disabled={saving}>{saving ? "Uploading…" : "Upload"}</Btn>
      </>}
    >
      {!existingDoc && (
        <>
          <Field label="Document Name">
            <Input value={form.name} onChange={e=>set("name",e.target.value)} placeholder="e.g. System Requirements v2"/>
          </Field>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
            <Field label="Category">
              <Select value={form.category} onChange={e=>set("category",e.target.value)}>
                {CATEGORIES.filter(c=>c!=="All").map(c=><option key={c}>{c}</option>)}
              </Select>
            </Field>
            <Field label="Visibility">
              <Select value={form.is_private?"private":"team"} onChange={e=>set("is_private",e.target.value==="private")}>
                <option value="team">Team (visible to all)</option>
                <option value="private">Private (only me)</option>
              </Select>
            </Field>
          </div>
          <Field label="Description">
            <Textarea value={form.description} onChange={e=>set("description",e.target.value)} placeholder="Brief description of this document…"/>
          </Field>
        </>
      )}

      <Field label={existingDoc ? "Change Note (what's new in this version)" : "Change Note"}>
        <Input value={form.change_note} onChange={e=>set("change_note",e.target.value)} placeholder="e.g. Updated section 3 with new API specs"/>
      </Field>

      <Field label="File">
        <div
          style={{ border:`1px dashed ${file ? T.accent : T.border2}`, borderRadius:3, padding:20, textAlign:"center", cursor:"pointer", background:file?"#00d4ff08":"transparent", transition:"all 0.15s" }}
          onClick={() => fileRef.current?.click()}
          onDragOver={e=>{ e.preventDefault(); }}
          onDrop={e=>{ e.preventDefault(); setFile(e.dataTransfer.files[0]); }}
        >
          <div style={{ fontFamily:T.mono, fontSize:11, color:file?T.accent:T.muted }}>
            {file ? `✓ ${file.name} (${fmt(file.size)})` : "Click or drag & drop file here"}
          </div>
          <input ref={fileRef} type="file" style={{ display:"none" }} onChange={e=>setFile(e.target.files[0])}/>
        </div>
      </Field>

      {error && <div style={{ fontFamily:T.mono, fontSize:11, color:T.red, marginTop:8 }}>{error}</div>}
    </Modal>
  );
}

// ── Edit Metadata Modal ───────────────────────────────────────────────────────
function EditModal({ doc, onDone, onClose }) {
  const [form, setForm] = useState({ name:doc.name, category:doc.category, description:doc.description, is_private:doc.is_private });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setForm(p=>({...p,[k]:v}));

  async function handleSave() {
    setSaving(true);
    try { await apiPatch(`/docs/${doc.id}`, form); onDone(); }
    catch(e) { alert(e.message); }
    finally { setSaving(false); }
  }

  return (
    <Modal title={`Edit Metadata // ${doc.name}`} onClose={onClose}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancel</Btn><Btn onClick={handleSave} disabled={saving}>{saving?"Saving…":"Save"}</Btn></>}>
      <Field label="Document Name"><Input value={form.name} onChange={e=>set("name",e.target.value)}/></Field>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
        <Field label="Category">
          <Select value={form.category} onChange={e=>set("category",e.target.value)}>
            {CATEGORIES.filter(c=>c!=="All").map(c=><option key={c}>{c}</option>)}
          </Select>
        </Field>
        <Field label="Visibility">
          <Select value={form.is_private?"private":"team"} onChange={e=>set("is_private",e.target.value==="private")}>
            <option value="team">Team (visible to all)</option>
            <option value="private">Private (only me)</option>
          </Select>
        </Field>
      </div>
      <Field label="Description"><Textarea value={form.description} onChange={e=>set("description",e.target.value)}/></Field>
    </Modal>
  );
}

// ── Version History Drawer ────────────────────────────────────────────────────
function VersionDrawer({ doc, currentUser, onNewVersion, onDeleted, onClose }) {
  const [deleting, setDeleting] = useState(null);

  async function handleDeleteVersion(v) {
    if (!confirm(`Delete version ${v.version_number}?`)) return;
    setDeleting(v.id);
    try { await apiDel(`/docs/${doc.id}/versions/${v.version_number}`); onDeleted(); }
    catch(e) { alert(e.message); }
    finally { setDeleting(null); }
  }

  const canManage = doc.owner_id === currentUser?.id || currentUser?.role === "manager";

  return (
    <Modal title={`Version History // ${doc.name}`} onClose={onClose}
      footer={<><Btn onClick={onNewVersion}>+ Upload New Version</Btn><Btn variant="ghost" onClick={onClose}>Close</Btn></>}>

      <div style={{ marginBottom:14, display:"flex", gap:10, flexWrap:"wrap" }}>
        <CatBadge cat={doc.category}/>
        <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>Owner: {doc.owner_name}</span>
        {doc.is_private && <span style={{ fontFamily:T.mono, fontSize:9, color:T.orange, border:`1px solid ${T.orange}55`, background:`${T.orange}12`, padding:"2px 7px", borderRadius:2 }}>🔒 Private</span>}
      </div>

      {doc.description && (
        <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, marginBottom:16, lineHeight:1.6, padding:"10px 12px", background:T.surface, borderRadius:3, border:`1px solid ${T.border}` }}>
          {doc.description}
        </div>
      )}

      <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
        {[...doc.versions].reverse().map(v => (
          <div key={v.id} style={{ padding:"12px 14px", background:T.surface, border:`1px solid ${v.is_latest ? T.accent+"44" : T.border}`, borderRadius:3, display:"flex", alignItems:"flex-start", gap:12 }}>
            <div style={{ fontFamily:T.mono, fontSize:18, fontWeight:600, color:v.is_latest?T.accent:T.muted, minWidth:32, textAlign:"center", lineHeight:1 }}>
              v{v.version_number}
            </div>
            <div style={{ flex:1 }}>
              <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4 }}>
                <span style={{ fontSize:12.5, fontWeight:500 }}>{v.filename}</span>
                {v.is_latest && <span style={{ fontFamily:T.mono, fontSize:9, color:T.accent, border:`1px solid ${T.accent}44`, padding:"1px 5px", borderRadius:2 }}>LATEST</span>}
              </div>
              <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted, lineHeight:1.8 }}>
                {v.change_note && <span style={{ color:T.text }}>"{v.change_note}"</span>}<br/>
                {fmt(v.size_bytes)} · {v.mime_type.split("/")[1]?.toUpperCase() || v.mime_type} · {v.uploaded_by_name} · {fmtDate(v.uploaded_at)}
              </div>
            </div>
            <div style={{ display:"flex", gap:6, flexShrink:0 }}>
              <Btn size="xs" onClick={() => apiDownload(doc.id, v.version_number, v.filename)}>⬇ Download</Btn>
              {canManage && !v.is_latest && (
                <Btn variant="danger" size="xs" disabled={deleting===v.id} onClick={() => handleDeleteVersion(v)}>
                  {deleting===v.id ? "…" : "Delete"}
                </Btn>
              )}
            </div>
          </div>
        ))}
      </div>
    </Modal>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function DocumentsPage({ user }) {
  const [docs,      setDocs]      = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [activeCat, setActiveCat] = useState("All");
  const [search,    setSearch]    = useState("");
  const [uploading, setUploading] = useState(false);
  const [versioning,setVersioning]= useState(null);   // doc to add version to
  const [editing,   setEditing]   = useState(null);   // doc to edit metadata
  const [viewing,   setViewing]   = useState(null);   // doc whose versions to show

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet(`/docs${activeCat !== "All" ? `?category=${encodeURIComponent(activeCat)}` : ""}`);
      setDocs(data);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, [activeCat]);

  useEffect(() => { load(); }, [load]);

  async function handleDelete(doc) {
    if (!confirm(`Delete "${doc.name}" and all ${doc.versions?.length} version(s)?`)) return;
    try { await apiDel(`/docs/${doc.id}`); await load(); }
    catch(e) { alert(e.message); }
  }

  const filtered = docs.filter(d =>
    !search || d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.owner_name.toLowerCase().includes(search.toLowerCase()) ||
    d.description.toLowerCase().includes(search.toLowerCase())
  );

  const canManage = (doc) => doc.owner_id === user?.id || user?.role === "manager";

  // Group by category for the summary strip
  const catCounts = docs.reduce((acc, d) => { acc[d.category] = (acc[d.category]||0)+1; return acc; }, {});

  return (
    <>
      {/* ── Page header ── */}
      <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", marginBottom:24, paddingBottom:16, borderBottom:`1px solid ${T.border}` }}>
        <div>
          <div style={{ fontFamily:T.mono, fontSize:18, fontWeight:500, letterSpacing:1 }}>DOCUMENTS</div>
          <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, marginTop:4 }}>
            {docs.length} document{docs.length!==1?"s":""} · Requirements · Design · Reviews · Reports · Change Requests
          </div>
        </div>
        <Btn onClick={() => setUploading(true)}>+ Upload Document</Btn>
      </div>

      {/* ── Category summary strip ── */}
      <div style={{ display:"flex", gap:10, flexWrap:"wrap", marginBottom:20 }}>
        {CATEGORIES.filter(c=>c!=="All").map(cat => (
          <div key={cat}
            onClick={() => setActiveCat(c => c===cat ? "All" : cat)}
            style={{ display:"flex", alignItems:"center", gap:6, padding:"6px 12px", borderRadius:3, border:`1px solid ${activeCat===cat ? CAT_COLORS[cat] : T.border}`, background:activeCat===cat ? CAT_COLORS[cat]+"18" : T.panel, cursor:"pointer", transition:"all 0.12s" }}
          >
            <span style={{ fontFamily:T.mono, fontSize:9, color: activeCat===cat ? CAT_COLORS[cat] : T.muted, letterSpacing:1 }}>{cat}</span>
            {catCounts[cat] && <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>({catCounts[cat]})</span>}
          </div>
        ))}
      </div>

      {/* ── Search ── */}
      <div style={{ marginBottom:16 }}>
        <input
          value={search} onChange={e=>setSearch(e.target.value)}
          placeholder="Search by name, owner, description…"
          style={{ width:"100%", background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3, padding:"8px 14px", color:T.text, fontFamily:T.sans, fontSize:13, outline:"none", boxSizing:"border-box" }}
        />
      </div>

      {/* ── Document list ── */}
      {loading
        ? <div style={{ fontFamily:T.mono, color:T.muted, padding:40, textAlign:"center" }}>Loading…</div>
        : filtered.length === 0
          ? <div style={{ fontFamily:T.mono, color:T.muted, padding:40, textAlign:"center" }}>
              {search ? "No documents match your search." : "No documents yet. Click Upload Document to get started."}
            </div>
          : (
            <div style={{ background:T.panel, border:`1px solid ${T.border}`, borderRadius:4, overflow:"hidden" }}>
              {/* Table header */}
              <div style={{ display:"grid", gridTemplateColumns:"2fr 130px 90px 80px 80px 140px 160px", gap:0, padding:"10px 16px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
                {["Document","Category","Version","Size","Privacy","Owner","Uploaded",""].map((h,i) => (
                  <div key={i} style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", textTransform:"uppercase", color:T.muted }}>{h}</div>
                ))}
              </div>

              {filtered.map((doc, idx) => (
                <div key={doc.id}
                  style={{ display:"grid", gridTemplateColumns:"2fr 130px 90px 80px 80px 140px auto", gap:0, padding:"12px 16px", borderBottom: idx<filtered.length-1?`1px solid ${T.border}`:"none", alignItems:"center", transition:"background 0.1s", cursor:"pointer" }}
                  onMouseEnter={e=>e.currentTarget.style.background="#ffffff04"}
                  onMouseLeave={e=>e.currentTarget.style.background="transparent"}
                >
                  {/* Name + description */}
                  <div>
                    <div style={{ fontWeight:500, fontSize:13, marginBottom:2 }}>{doc.name}</div>
                    {doc.description && <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>{doc.description.slice(0,60)}{doc.description.length>60?"…":""}</div>}
                  </div>

                  {/* Category */}
                  <div><CatBadge cat={doc.category}/></div>

                  {/* Version */}
                  <div>
                    <span
                      style={{ fontFamily:T.mono, fontSize:11, color:T.accent, cursor:"pointer", textDecoration:"underline" }}
                      onClick={() => setViewing(doc)}
                      title="Click to view version history"
                    >
                      v{doc.latest_version} {doc.latest_version > 1 && <span style={{ color:T.muted }}>({doc.latest_version} ver)</span>}
                    </span>
                  </div>

                  {/* Size */}
                  <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>{fmt(doc.size_bytes)}</div>

                  {/* Privacy */}
                  <div>
                    {doc.is_private
                      ? <span style={{ fontFamily:T.mono, fontSize:9, color:T.orange }}>🔒 Private</span>
                      : <span style={{ fontFamily:T.mono, fontSize:9, color:T.green }}>🌐 Team</span>
                    }
                  </div>

                  {/* Owner */}
                  <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>{doc.owner_name}</div>

                  {/* Uploaded */}
                  <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>{fmtDate(doc.uploaded_at)}</div>

                  {/* Actions */}
                  <div style={{ display:"flex", gap:6, justifyContent:"flex-end" }}>
                    <Btn size="xs" onClick={() => apiDownload(doc.id, doc.latest_version, doc.filename)} title="Download latest version">⬇</Btn>
                    <Btn size="xs" variant="ghost" onClick={() => setViewing(doc)} title="Version history">History</Btn>
                    <Btn size="xs" variant="ghost" onClick={() => setVersioning(doc)} title="Upload new version">+ Ver</Btn>
                    {canManage(doc) && <>
                      <Btn size="xs" variant="ghost" onClick={() => setEditing(doc)} title="Edit metadata">✎</Btn>
                      <Btn size="xs" variant="danger" onClick={() => handleDelete(doc)} title="Delete document">✕</Btn>
                    </>}
                  </div>
                </div>
              ))}
            </div>
          )
      }

      {/* ── Modals ── */}
      {uploading   && <UploadModal onDone={()=>{ setUploading(false);  load(); }} onClose={()=>setUploading(false)}/>}
      {versioning  && <UploadModal existingDoc={versioning} onDone={()=>{ setVersioning(null); load(); }} onClose={()=>setVersioning(null)}/>}
      {editing     && <EditModal   doc={editing} onDone={()=>{ setEditing(null); load(); }} onClose={()=>setEditing(null)} currentUser={user}/>}
      {viewing     && <VersionDrawer doc={viewing} currentUser={user}
                        onNewVersion={()=>{ setVersioning(viewing); setViewing(null); }}
                        onDeleted={()=>{ load(); setViewing(null); }}
                        onClose={()=>setViewing(null)}/>}
    </>
  );
}
