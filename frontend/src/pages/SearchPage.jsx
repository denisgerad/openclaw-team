/**
 * openclaw/frontend/src/pages/SearchPage.jsx
 *
 * Semantic Search & Document Intelligence — Step 2 UI
 *
 * Tabs:
 *  1. Search       — query across all docs, show ranked results + Mistral synthesis
 *  2. Summarise    — pick a document version, generate structured summary
 *  3. Compare      — pick a doc + two versions, get semantic diff report
 *  4. Index Status — show which versions are indexed / pending / failed
 */
import { useState, useEffect, useCallback } from "react";
import { T, Btn, Field, Select } from "../components/Sidebar";

// ── inline API ────────────────────────────────────────────────────────────────
function token() { return localStorage.getItem("oc_token"); }
const hdr = () => ({ "Content-Type": "application/json", Authorization: `Bearer ${token()}` });

async function apiFetch(method, path, body) {
  const res = await fetch(`/api${path}`, { method, headers: hdr(), body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail); }
  return res.json();
}
const apiGet  = p      => apiFetch("GET", p);
const apiPost = (p, b) => apiFetch("POST", p, b);

// ── Constants ─────────────────────────────────────────────────────────────────
const CATEGORIES = ["All", "Requirements", "Design", "Review", "Report", "Change Request", "Test Plan", "Architecture", "Meeting Notes", "Other"];
const CAT_COLORS = { Requirements:"#7dd3fc", Design:"#c4b5fd", Review:"#86efac", Report:"#fcd34d", "Change Request":"#f9a8d4", "Test Plan":"#6ee7b7", Architecture:"#93c5fd", "Meeting Notes":"#d9f99d", Other:"#cbd5e1" };

const STATUS_COLOR = { indexed:"#00d68f", pending:"#ff8c00", failed:"#ff3b3b", skipped:"#4a5a6a" };
const STATUS_ICON  = { indexed:"✓", pending:"⟳", failed:"✕", skipped:"—" };

function fmt(n) { return n?.toLocaleString() ?? "—"; }
function score2pct(s) { return `${Math.round(s * 100)}%`; }

// ── Shared components ─────────────────────────────────────────────────────────

function Panel({ children, style={} }) {
  return <div style={{ background:T.panel, border:`1px solid ${T.border}`, borderRadius:4, overflow:"hidden", ...style }}>{children}</div>;
}

function SectionHeader({ title, sub }) {
  return (
    <div style={{ marginBottom:20, paddingBottom:14, borderBottom:`1px solid ${T.border}` }}>
      <div style={{ fontFamily:T.mono, fontSize:15, fontWeight:500, letterSpacing:1 }}>{title}</div>
      {sub && <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, marginTop:4 }}>{sub}</div>}
    </div>
  );
}

function Spinner() {
  return <span style={{ display:"inline-block", animation:"spin 1s linear infinite" }}>⟳</span>;
}

function CatBadge({ cat }) {
  const color = CAT_COLORS[cat] || "#cbd5e1";
  return <span style={{ fontFamily:T.mono, fontSize:9, padding:"2px 6px", borderRadius:2, background:color+"22", border:`1px solid ${color}55`, color, whiteSpace:"nowrap" }}>{cat}</span>;
}

function ScoreBar({ score }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? T.green : pct >= 45 ? T.orange : T.muted;
  return (
    <div style={{ display:"flex", alignItems:"center", gap:8 }}>
      <div style={{ width:60, height:4, background:T.border, borderRadius:2, overflow:"hidden" }}>
        <div style={{ width:`${pct}%`, height:"100%", background:color, borderRadius:2 }}/>
      </div>
      <span style={{ fontFamily:T.mono, fontSize:9, color }}>{pct}%</span>
    </div>
  );
}

// ── TAB 1: Semantic Search ────────────────────────────────────────────────────

function SearchTab() {
  const [query,     setQuery]    = useState("");
  const [category,  setCategory] = useState("All");
  const [nResults,  setNResults] = useState(8);
  const [summarise, setSummarise]= useState(true);
  const [loading,   setLoading]  = useState(false);
  const [results,   setResults]  = useState(null);
  const [error,     setError]    = useState(null);

  async function handleSearch(e) {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true); setError(null); setResults(null);
    try {
      const data = await apiPost("/search", {
        query,
        category: category === "All" ? null : category,
        n_results: nResults,
        summarise,
      });
      setResults(data);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }

  return (
    <>
      <SectionHeader title="SEMANTIC SEARCH" sub="Natural language search across all indexed documents · Powered by Mistral embeddings"/>

      {/* Search form */}
      <Panel style={{ marginBottom:20 }}>
        <div style={{ padding:20 }}>
          <form onSubmit={handleSearch}>
            <div style={{ display:"flex", gap:10, marginBottom:14 }}>
              <input
                value={query} onChange={e=>setQuery(e.target.value)}
                placeholder='Ask anything — e.g. "What are the authentication requirements?" or "Show API rate limits"'
                style={{ flex:1, background:T.surface, border:`1px solid ${T.accent}44`, borderRadius:3, padding:"10px 14px", color:T.text, fontFamily:T.sans, fontSize:13, outline:"none" }}
              />
              <Btn onClick={handleSearch} disabled={loading || !query.trim()}>
                {loading ? <Spinner/> : "⌕"} Search
              </Btn>
            </div>
            <div style={{ display:"flex", gap:16, alignItems:"center" }}>
              <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>Category:</span>
                <select value={category} onChange={e=>setCategory(e.target.value)}
                  style={{ background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3, padding:"4px 8px", color:T.text, fontFamily:T.mono, fontSize:10, outline:"none" }}>
                  {CATEGORIES.map(c=><option key={c}>{c}</option>)}
                </select>
              </div>
              <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>Results:</span>
                <select value={nResults} onChange={e=>setNResults(Number(e.target.value))}
                  style={{ background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3, padding:"4px 8px", color:T.text, fontFamily:T.mono, fontSize:10, outline:"none" }}>
                  {[4,8,12,16].map(n=><option key={n}>{n}</option>)}
                </select>
              </div>
              <label style={{ display:"flex", alignItems:"center", gap:6, cursor:"pointer" }}>
                <input type="checkbox" checked={summarise} onChange={e=>setSummarise(e.target.checked)}/>
                <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>AI Synthesis</span>
              </label>
            </div>
          </form>
        </div>
      </Panel>

      {error && <div style={{ fontFamily:T.mono, fontSize:12, color:T.red, marginBottom:16 }}>{error}</div>}

      {results && (
        <>
          {/* AI synthesis */}
          {results.summary && (
            <Panel style={{ marginBottom:20, borderLeft:`3px solid ${T.accent}` }}>
              <div style={{ padding:16 }}>
                <div style={{ fontFamily:T.mono, fontSize:10, letterSpacing:2, color:T.accent, textTransform:"uppercase", marginBottom:10 }}>
                  ✦ AI Synthesis — "{results.query}"
                </div>
                <div style={{ fontSize:13, lineHeight:1.7, color:T.text, whiteSpace:"pre-wrap" }}>{results.summary}</div>
              </div>
            </Panel>
          )}

          {/* Result count */}
          <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted, marginBottom:12 }}>
            {results.total_hits} chunk{results.total_hits!==1?"s":""} matched · sorted by relevance
          </div>

          {/* Results list */}
          {results.results.length === 0
            ? <div style={{ fontFamily:T.mono, color:T.muted, padding:40, textAlign:"center" }}>No results found. Try a different query or upload and index more documents.</div>
            : <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
                {results.results.map((r, i) => (
                  <Panel key={r.chunk_id}>
                    <div style={{ padding:"12px 16px" }}>
                      <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", marginBottom:8, gap:12 }}>
                        <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap" }}>
                          <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>#{i+1}</span>
                          <span style={{ fontWeight:500, fontSize:13 }}>{r.doc_name}</span>
                          <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>v{r.version_number} · {r.filename}</span>
                          <CatBadge cat={r.category}/>
                          {r.page_hint && <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>p.{r.page_hint}</span>}
                        </div>
                        <ScoreBar score={r.score}/>
                      </div>
                      <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, lineHeight:1.7, background:T.surface, padding:"10px 12px", borderRadius:3, borderLeft:`2px solid ${T.border2}`, whiteSpace:"pre-wrap" }}>
                        {r.text}
                      </div>
                    </div>
                  </Panel>
                ))}
              </div>
          }
        </>
      )}
    </>
  );
}


// ── TAB 2: Summarise ──────────────────────────────────────────────────────────

function SummariseTab() {
  const [docs,     setDocs]    = useState([]);
  const [docId,    setDocId]   = useState("");
  const [versionId,setVersionId]= useState("");
  const [loading,  setLoading] = useState(false);
  const [result,   setResult]  = useState(null);
  const [error,    setError]   = useState(null);

  useEffect(() => {
    apiGet("/docs").then(setDocs).catch(console.error);
  }, []);

  const selectedDoc = docs.find(d => String(d.id) === String(docId));
  const versions    = selectedDoc?.versions || [];

  async function handleSummarise() {
    if (!versionId) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const data = await apiPost(`/search/summarise/${versionId}`);
      setResult(data);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }

  return (
    <>
      <SectionHeader title="DOCUMENT SUMMARISE" sub="Generate a structured AI summary of any document version"/>

      <Panel style={{ marginBottom:20 }}>
        <div style={{ padding:20 }}>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr auto", gap:14, alignItems:"flex-end" }}>
            <Field label="Document">
              <select value={docId} onChange={e=>{ setDocId(e.target.value); setVersionId(""); }}
                style={{ width:"100%", background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3, padding:"8px 12px", color:T.text, fontFamily:T.sans, fontSize:13, outline:"none" }}>
                <option value="">— Select document —</option>
                {docs.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </Field>
            <Field label="Version">
              <select value={versionId} onChange={e=>setVersionId(e.target.value)}
                style={{ width:"100%", background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3, padding:"8px 12px", color:T.text, fontFamily:T.sans, fontSize:13, outline:"none" }}>
                <option value="">— Select version —</option>
                {versions.map(v=><option key={v.id} value={v.id}>v{v.version_number} — {v.filename}{v.is_latest?" (latest)":""}</option>)}
              </select>
            </Field>
            <Btn onClick={handleSummarise} disabled={!versionId || loading} style={{ marginBottom:0, alignSelf:"flex-end" }}>
              {loading ? <Spinner/> : "✦"} Summarise
            </Btn>
          </div>
        </div>
      </Panel>

      {error && <div style={{ fontFamily:T.mono, fontSize:12, color:T.red, marginBottom:16 }}>{error}</div>}

      {result && (
        <Panel>
          <div style={{ padding:"12px 16px", borderBottom:`1px solid ${T.border}`, background:T.surface, display:"flex", gap:12, alignItems:"center" }}>
            <span style={{ fontFamily:T.mono, fontSize:11, letterSpacing:2, color:T.accent, textTransform:"uppercase" }}>Summary</span>
            <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>{result.doc_name} · v{result.version_number} · {result.filename}</span>
            <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted, marginLeft:"auto" }}>{fmt(result.char_count)} chars extracted</span>
          </div>
          <div style={{ padding:20 }}>
            <div style={{ fontSize:13, lineHeight:1.8, color:T.text, whiteSpace:"pre-wrap" }}>{result.summary}</div>
          </div>
        </Panel>
      )}
    </>
  );
}


// ── TAB 3: Compare Versions ───────────────────────────────────────────────────

const VERDICT_COLORS = {
  "Minor update":      T.green,
  "Moderate revision": T.yellow,
  "Major revision":    T.orange,
  "Complete rewrite":  T.red,
};

function CompareTab() {
  const [docs,    setDocs]   = useState([]);
  const [docId,   setDocId]  = useState("");
  const [vA,      setVA]     = useState("");
  const [vB,      setVB]     = useState("");
  const [loading, setLoading]= useState(false);
  const [result,  setResult] = useState(null);
  const [error,   setError]  = useState(null);

  useEffect(() => { apiGet("/docs").then(setDocs).catch(console.error); }, []);

  const selectedDoc = docs.find(d => String(d.id) === String(docId));
  const versions    = selectedDoc?.versions || [];

  async function handleCompare() {
    if (!docId || !vA || !vB || vA === vB) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const data = await apiPost("/search/compare", {
        doc_id: Number(docId),
        version_a: Number(vA),
        version_b: Number(vB),
      });
      setResult(data);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }

  const cmp = result?.comparison;
  const verdictColor = cmp ? VERDICT_COLORS[cmp.verdict] || T.muted : T.muted;

  return (
    <>
      <SectionHeader title="VERSION COMPARISON" sub="Semantic diff between two versions of the same document · Powered by Mistral"/>

      <Panel style={{ marginBottom:20 }}>
        <div style={{ padding:20 }}>
          <div style={{ display:"grid", gridTemplateColumns:"2fr 1fr 1fr auto", gap:14, alignItems:"flex-end" }}>
            <Field label="Document">
              <select value={docId} onChange={e=>{ setDocId(e.target.value); setVA(""); setVB(""); }}
                style={{ width:"100%", background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3, padding:"8px 12px", color:T.text, fontFamily:T.sans, fontSize:13, outline:"none" }}>
                <option value="">— Select document —</option>
                {docs.filter(d=>d.latest_version>1).map(d=><option key={d.id} value={d.id}>{d.name} ({d.latest_version} versions)</option>)}
              </select>
            </Field>
            <Field label="Version A (older)">
              <select value={vA} onChange={e=>setVA(e.target.value)}
                style={{ width:"100%", background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3, padding:"8px 12px", color:T.text, fontFamily:T.sans, fontSize:13, outline:"none" }}>
                <option value="">— v? —</option>
                {versions.map(v=><option key={v.version_number} value={v.version_number}>v{v.version_number}</option>)}
              </select>
            </Field>
            <Field label="Version B (newer)">
              <select value={vB} onChange={e=>setVB(e.target.value)}
                style={{ width:"100%", background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3, padding:"8px 12px", color:T.text, fontFamily:T.sans, fontSize:13, outline:"none" }}>
                <option value="">— v? —</option>
                {versions.map(v=><option key={v.version_number} value={v.version_number}>v{v.version_number}</option>)}
              </select>
            </Field>
            <Btn onClick={handleCompare} disabled={!docId||!vA||!vB||vA===vB||loading} style={{ alignSelf:"flex-end" }}>
              {loading ? <Spinner/> : "⇄"} Compare
            </Btn>
          </div>
          {vA && vB && vA === vB && <div style={{ fontFamily:T.mono, fontSize:10, color:T.orange, marginTop:8 }}>Select two different versions to compare</div>}
        </div>
      </Panel>

      {error && <div style={{ fontFamily:T.mono, fontSize:12, color:T.red, marginBottom:16 }}>{error}</div>}

      {cmp && (
        <>
          {/* Verdict banner */}
          <div style={{ display:"flex", alignItems:"center", gap:12, padding:"12px 16px", background:verdictColor+"18", border:`1px solid ${verdictColor}44`, borderRadius:4, marginBottom:16 }}>
            <span style={{ fontFamily:T.mono, fontSize:18, color:verdictColor }}>⇄</span>
            <div>
              <div style={{ fontFamily:T.mono, fontSize:12, fontWeight:600, color:verdictColor }}>{cmp.verdict}</div>
              <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>
                {result.doc_name} · v{result.version_a} → v{result.version_b}
              </div>
            </div>
          </div>

          {/* Summary */}
          <Panel style={{ marginBottom:14, borderLeft:`3px solid ${T.accent}` }}>
            <div style={{ padding:14 }}>
              <div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:2, color:T.accent, textTransform:"uppercase", marginBottom:8 }}>Overview</div>
              <div style={{ fontSize:13, lineHeight:1.7, color:T.text }}>{cmp.summary}</div>
            </div>
          </Panel>

          {/* Diff grid */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:12 }}>
            {[
              { label:"Added in v" + result.version_b, value:cmp.added,     color:T.green  },
              { label:"Removed from v" + result.version_a, value:cmp.removed, color:T.red },
            ].map(item => (
              <Panel key={item.label}>
                <div style={{ padding:14 }}>
                  <div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:2, color:item.color, textTransform:"uppercase", marginBottom:8 }}>{item.label}</div>
                  <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, lineHeight:1.7, whiteSpace:"pre-wrap" }}>{item.value || "—"}</div>
                </div>
              </Panel>
            ))}
          </div>

          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
            {[
              { label:"Changed",   value:cmp.changed,   color:T.orange },
              { label:"Unchanged", value:cmp.unchanged, color:T.muted  },
            ].map(item => (
              <Panel key={item.label}>
                <div style={{ padding:14 }}>
                  <div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:2, color:item.color, textTransform:"uppercase", marginBottom:8 }}>{item.label}</div>
                  <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, lineHeight:1.7, whiteSpace:"pre-wrap" }}>{item.value || "—"}</div>
                </div>
              </Panel>
            ))}
          </div>
        </>
      )}
    </>
  );
}


// ── TAB 4: Index Status ───────────────────────────────────────────────────────

function IndexTab({ user }) {
  const [rows,    setRows]    = useState([]);
  const [stats,   setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [status, st] = await Promise.all([apiGet("/search/index-status"), apiGet("/search/stats")]);
      setRows(status);
      setStats(st);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleReindexOne(versionId) {
    try {
      await apiPost(`/search/reindex/${versionId}`);
      setTimeout(load, 2000);
    } catch(e) { alert(e.message); }
  }

  async function handleReindexAll() {
    if (!confirm("Re-index all document versions? This may take a while.")) return;
    setReindexing(true);
    try { await apiPost("/search/reindex-all"); setTimeout(load, 3000); }
    catch(e) { alert(e.message); }
    finally { setReindexing(false); }
  }

  const indexed = rows.filter(r=>r.index_status==="indexed").length;
  const pending = rows.filter(r=>r.index_status==="pending").length;
  const failed  = rows.filter(r=>r.index_status==="failed").length;

  return (
    <>
      <SectionHeader title="INDEX STATUS" sub="ChromaDB embedding index — track which document versions are searchable"/>

      {/* Stats bar */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:20 }}>
        {[
          { label:"Total Chunks", value:stats?.total_chunks ?? "—", color:T.accent },
          { label:"Indexed",      value:indexed,                     color:T.green  },
          { label:"Pending",      value:pending,                     color:T.orange },
          { label:"Failed",       value:failed,                      color:failed>0?T.red:T.muted },
        ].map(c=>(
          <Panel key={c.label}>
            <div style={{ padding:"12px 14px" }}>
              <div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", color:T.muted, textTransform:"uppercase", marginBottom:6 }}>{c.label}</div>
              <div style={{ fontFamily:T.mono, fontSize:22, fontWeight:600, color:c.color }}>{fmt(c.value)}</div>
            </div>
          </Panel>
        ))}
      </div>

      <div style={{ display:"flex", justifyContent:"flex-end", marginBottom:14, gap:10 }}>
        <Btn variant="ghost" size="sm" onClick={load}>⟳ Refresh</Btn>
        {user?.role === "manager" && (
          <Btn size="sm" onClick={handleReindexAll} disabled={reindexing}>
            {reindexing ? <Spinner/> : "↺"} Re-index All
          </Btn>
        )}
      </div>

      {loading
        ? <div style={{ fontFamily:T.mono, color:T.muted, padding:40, textAlign:"center" }}>Loading…</div>
        : (
          <Panel>
            <div style={{ padding:"10px 16px", borderBottom:`1px solid ${T.border}`, background:T.surface, display:"grid", gridTemplateColumns:"2fr 120px 80px 80px 80px 100px 120px 80px", gap:0 }}>
              {["Document","Category","Version","File","Chunks","Chars","Indexed At",""].map((h,i)=>(
                <span key={i} style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", textTransform:"uppercase", color:T.muted }}>{h}</span>
              ))}
            </div>
            {rows.map((r,i)=>(
              <div key={r.version_id}
                style={{ display:"grid", gridTemplateColumns:"2fr 120px 80px 80px 80px 100px 120px 80px", gap:0, padding:"10px 16px", borderBottom:i<rows.length-1?`1px solid ${T.border}`:"none", alignItems:"center" }}>
                <div style={{ fontWeight:500, fontSize:12 }}>{r.doc_name}</div>
                <div><CatBadge cat={r.category}/></div>
                <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted }}>v{r.version_number}</div>
                <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>{r.filename.slice(0,12)}{r.filename.length>12?"…":""}</div>
                <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted }}>{r.chunk_count || "—"}</div>
                <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted }}>{r.char_count ? `${(r.char_count/1000).toFixed(1)}k` : "—"}</div>
                <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>
                  {r.indexed_at ? new Date(r.indexed_at).toLocaleString("en-GB",{hour12:false,hour:"2-digit",minute:"2-digit",day:"2-digit",month:"short"}) : "—"}
                </div>
                <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                  <span style={{ fontFamily:T.mono, fontSize:10, color:STATUS_COLOR[r.index_status]||T.muted }}>{STATUS_ICON[r.index_status]} {r.index_status}</span>
                  {r.index_status !== "indexed" && (
                    <button onClick={()=>handleReindexOne(r.version_id)} title="Re-index this version"
                      style={{ background:"none", border:"none", color:T.accent, cursor:"pointer", fontFamily:T.mono, fontSize:10 }}>↺</button>
                  )}
                </div>
              </div>
            ))}
          </Panel>
        )
      }
      {stats?.storage && <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted, marginTop:10 }}>ChromaDB storage: {stats.storage}</div>}
    </>
  );
}


// ── Main Page ─────────────────────────────────────────────────────────────────

const TABS = [
  { id:"search",    label:"⌕  Search"   },
  { id:"summarise", label:"✦  Summarise" },
  { id:"compare",   label:"⇄  Compare"  },
  { id:"index",     label:"◈  Index Status" },
];

export default function SearchPage({ user }) {
  const [tab, setTab] = useState("search");

  return (
    <>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <div style={{ marginBottom:24, paddingBottom:0, borderBottom:`1px solid ${T.border}` }}>
        <div style={{ fontFamily:T.mono, fontSize:18, fontWeight:500, letterSpacing:1, marginBottom:16 }}>
          SEMANTIC INTELLIGENCE
        </div>
        <div style={{ display:"flex", gap:0 }}>
          {TABS.map(t=>(
            <div key={t.id} onClick={()=>setTab(t.id)}
              style={{ fontFamily:T.mono, fontSize:11, letterSpacing:1, padding:"10px 18px", cursor:"pointer", color:tab===t.id?T.accent:T.muted, borderBottom:tab===t.id?`2px solid ${T.accent}`:"2px solid transparent", marginBottom:-1, transition:"all 0.12s" }}>
              {t.label}
            </div>
          ))}
        </div>
      </div>

      {tab === "search"    && <SearchTab/>}
      {tab === "summarise" && <SummariseTab/>}
      {tab === "compare"   && <CompareTab/>}
      {tab === "index"     && <IndexTab user={user}/>}
    </>
  );
}
