/**
 * openclaw/frontend/src/pages/ComplexityPage.jsx
 *
 * Complexity Analyser UI
 *
 * Layout:
 *  Top     — document list with overall rating + trigger analyse button
 *  Drill-down panel — section table with rating chips + expand per section
 *  Factor panel     — per-section factors with category, weight, evidence
 *  Stats sidebar    — factor frequency + rating distribution across all docs
 */
import { useState, useEffect, useCallback } from "react";
import { T, Btn } from "../components/Sidebar";

// ── inline API ────────────────────────────────────────────────────────────────
const hdr = () => ({ "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("oc_token")}` });
async function apiFetch(method, path, body) {
  const res = await fetch(`/api${path}`, { method, headers: hdr(), body: body ? JSON.stringify(body) : undefined });
  if (res.status === 204) return null;
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail); }
  return res.json();
}
const apiGet  = p      => apiFetch("GET",    p);
const apiPost = (p, b) => apiFetch("POST",   p, b);
const apiDel  = p      => apiFetch("DELETE", p);

// ── Constants ─────────────────────────────────────────────────────────────────
const RATING_COLOR = {
  Simple:   "#00d68f",
  Moderate: "#f5c400",
  Complex:  "#ff8c00",
  Critical: "#ff3b3b",
  Unknown:  "#4a5a6a",
  Pending:  "#4a5a6a",
};
const RATING_BG = {
  Simple:   "#00d68f18",
  Moderate: "#f5c40018",
  Complex:  "#ff8c0018",
  Critical: "#ff3b3b18",
  Unknown:  "#4a5a6a18",
  Pending:  "#4a5a6a18",
};
const RATING_ICON = { Simple:"🟢", Moderate:"🟡", Complex:"🟠", Critical:"🔴", Unknown:"⚪", Pending:"⟳" };
const WEIGHT_LABEL = { 1:"Minor", 2:"Significant", 3:"Critical" };
const WEIGHT_COLOR = { 1: T.muted, 2: T.orange, 3: T.red };

const CAT_COLORS = {
  "Algorithm & Logic":       "#7dd3fc",
  "Interface & Integration": "#c4b5fd",
  "Data Complexity":         "#fcd34d",
  "Concurrency & Performance":"#f9a8d4",
  "Security & Compliance":   "#ff3b3b",
  "UI & UX Complexity":      "#86efac",
  "Dependency & Environment":"#93c5fd",
  "Testing & Verification":  "#d9f99d",
};

function fmt(n) { return typeof n === "number" ? n.toFixed(1) : "—"; }
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", { hour12:false, day:"2-digit", month:"short", hour:"2-digit", minute:"2-digit" });
}

// ── Shared UI ─────────────────────────────────────────────────────────────────
function Panel({ children, style={} }) {
  return <div style={{ background:T.panel, border:`1px solid ${T.border}`, borderRadius:4, overflow:"hidden", ...style }}>{children}</div>;
}
function PanelHdr({ children }) {
  return <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"10px 16px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>{children}</div>;
}
function PanelTitle({ children, color }) {
  return <span style={{ fontFamily:T.mono, fontSize:11, letterSpacing:2, color:color||T.accent, textTransform:"uppercase" }}>{children}</span>;
}

function RatingChip({ rating, score, size="md" }) {
  const color = RATING_COLOR[rating] || T.muted;
  const bg    = RATING_BG[rating]    || "#4a5a6a18";
  const pad   = size === "sm" ? "2px 8px" : "4px 12px";
  const fs    = size === "sm" ? 9 : 11;
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:6, padding:pad, borderRadius:3, border:`1px solid ${color}55`, background:bg, fontFamily:T.mono, fontSize:fs, fontWeight:600, color, whiteSpace:"nowrap" }}>
      {RATING_ICON[rating]} {rating}{score !== undefined ? ` (${score})` : ""}
    </span>
  );
}

function ConfidenceBar({ value }) {
  const pct   = Math.round(value * 100);
  const color = pct >= 80 ? T.green : pct >= 60 ? T.yellow : T.orange;
  return (
    <div style={{ display:"flex", alignItems:"center", gap:6 }}>
      <div style={{ width:48, height:3, background:T.border, borderRadius:2, overflow:"hidden" }}>
        <div style={{ width:`${pct}%`, height:"100%", background:color }}/>
      </div>
      <span style={{ fontFamily:T.mono, fontSize:9, color }}>{pct}%</span>
    </div>
  );
}

function CatTag({ cat }) {
  const color = CAT_COLORS[cat] || "#cbd5e1";
  return <span style={{ fontFamily:T.mono, fontSize:9, padding:"2px 6px", borderRadius:2, background:color+"22", border:`1px solid ${color}55`, color, whiteSpace:"nowrap" }}>{cat}</span>;
}

// ── Factor drill-down row ─────────────────────────────────────────────────────
function FactorRow({ factor }) {
  return (
    <div style={{ display:"grid", gridTemplateColumns:"2fr 160px 80px 1fr", gap:12, padding:"8px 12px", borderBottom:`1px solid ${T.border}`, alignItems:"start" }}>
      <div style={{ fontFamily:T.mono, fontSize:11, color:T.text }}>{factor.factor}</div>
      <div><CatTag cat={factor.category}/></div>
      <div style={{ fontFamily:T.mono, fontSize:10, color:WEIGHT_COLOR[factor.weight]||T.muted }}>{WEIGHT_LABEL[factor.weight]}</div>
      <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted, fontStyle:"italic" }}>"{factor.evidence}"</div>
    </div>
  );
}

// ── Section row with expand ───────────────────────────────────────────────────
function SectionRow({ section, isExpanded, onToggle }) {
  const color = RATING_COLOR[section.rating] || T.muted;
  return (
    <>
      <div
        onClick={onToggle}
        style={{ display:"grid", gridTemplateColumns:"60px 2fr 130px 70px 110px 160px 28px", gap:0, padding:"10px 16px", borderBottom:`1px solid ${T.border}`, alignItems:"center", cursor:"pointer", transition:"background 0.1s", background:isExpanded?"#00d4ff06":"transparent" }}
        onMouseEnter={e=>!isExpanded&&(e.currentTarget.style.background="#ffffff04")}
        onMouseLeave={e=>!isExpanded&&(e.currentTarget.style.background="transparent")}
      >
        <div style={{ fontFamily:T.mono, fontSize:10, fontWeight:600, color:T.accent }}>{section.section_id}</div>
        <div><div style={{ fontSize:12.5, fontWeight:500, color:T.text }}>{section.title}</div></div>
        <div><RatingChip rating={section.rating} size="sm"/></div>
        <div style={{ fontFamily:T.mono, fontSize:12, fontWeight:600, color, textAlign:"center" }}>{section.score}</div>
        <div><ConfidenceBar value={section.confidence}/></div>
        <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>
          {section.factors.length} factor{section.factors.length!==1?"s":""}
        </div>
        <div style={{ fontFamily:T.mono, fontSize:12, color:T.muted, textAlign:"center" }}>
          {isExpanded ? "▲" : "▼"}
        </div>
      </div>

      {isExpanded && (
        <div style={{ borderBottom:`1px solid ${T.border}`, background:"#00d4ff04" }}>
          {/* Summary */}
          <div style={{ padding:"12px 16px", borderBottom:`1px solid ${T.border}` }}>
            <div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:2, color:T.muted, textTransform:"uppercase", marginBottom:6 }}>AI Assessment</div>
            <div style={{ fontSize:12.5, lineHeight:1.7, color:T.text }}>{section.summary}</div>
          </div>

          {/* Factors table */}
          {section.factors.length > 0 && (
            <div>
              <div style={{ display:"grid", gridTemplateColumns:"2fr 160px 80px 1fr", gap:12, padding:"8px 12px", borderBottom:`1px solid ${T.border}` }}>
                {["Factor","Category","Weight","Evidence"].map(h=>(
                  <span key={h} style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", textTransform:"uppercase", color:T.muted }}>{h}</span>
                ))}
              </div>
              {section.factors.map(f=><FactorRow key={f.id} factor={f}/>)}
            </div>
          )}

          <RawTextAccordion text={section.raw_text}/>
        </div>
      )}
    </>
  );
}

function RawTextAccordion({ text }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <div style={{ padding:"8px 16px", borderTop:`1px solid ${T.border}` }}>
      <div onClick={()=>setOpen(o=>!o)} style={{ fontFamily:T.mono, fontSize:9, letterSpacing:1.5, color:T.muted, cursor:"pointer", textTransform:"uppercase", display:"flex", alignItems:"center", gap:8 }}>
        {open ? "▲" : "▼"} Source Text
      </div>
      {open && (
        <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted, lineHeight:1.7, whiteSpace:"pre-wrap", marginTop:8, padding:"10px 12px", background:T.surface, borderRadius:3, border:`1px solid ${T.border}`, maxHeight:200, overflowY:"auto" }}>
          {text}
        </div>
      )}
    </div>
  );
}

// ── Stats sidebar ─────────────────────────────────────────────────────────────
function StatsPanel({ stats }) {
  if (!stats) return null;
  const ratings = stats.rating_distribution || {};
  const factors = stats.factor_frequency    || {};
  const total   = stats.total_documents || 0;

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
      <Panel>
        <PanelHdr><PanelTitle>Rating Distribution</PanelTitle><span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>{total} docs</span></PanelHdr>
        <div style={{ padding:14 }}>
          {["Critical","Complex","Moderate","Simple"].map(r=>{
            const count = ratings[r] || 0;
            const pct   = total > 0 ? (count / total) * 100 : 0;
            const color = RATING_COLOR[r];
            return (
              <div key={r} style={{ marginBottom:10 }}>
                <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                  <span style={{ fontFamily:T.mono, fontSize:10, color }}>{RATING_ICON[r]} {r}</span>
                  <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>{count}</span>
                </div>
                <div style={{ width:"100%", height:4, background:T.border, borderRadius:2, overflow:"hidden" }}>
                  <div style={{ width:`${pct}%`, height:"100%", background:color, borderRadius:2 }}/>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

      <Panel>
        <PanelHdr><PanelTitle>Top Factor Categories</PanelTitle></PanelHdr>
        <div style={{ padding:14 }}>
          {Object.entries(factors).slice(0,8).map(([cat, count])=>(
            <div key={cat} style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:8 }}>
              <span style={{ fontFamily:T.mono, fontSize:9, color:CAT_COLORS[cat]||T.muted, flex:1, marginRight:8 }}>{cat}</span>
              <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted, flexShrink:0 }}>{count}</span>
            </div>
          ))}
          {Object.keys(factors).length === 0 && <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>No data yet</span>}
        </div>
      </Panel>
    </div>
  );
}

// ── Document list row ─────────────────────────────────────────────────────────
function DocRow({ doc, isSelected, onSelect, onAnalyse, onDelete, analysing }) {
  const isAnalysing = analysing === doc.version_id;
  return (
    <div
      onClick={onSelect}
      style={{ display:"grid", gridTemplateColumns:"2fr 110px 100px 80px 80px 120px 120px", gap:0, padding:"11px 16px", borderBottom:`1px solid ${T.border}`, alignItems:"center", cursor:"pointer", background:isSelected?"#00d4ff06":"transparent", transition:"background 0.1s" }}
      onMouseEnter={e=>!isSelected&&(e.currentTarget.style.background="#ffffff04")}
      onMouseLeave={e=>!isSelected&&(e.currentTarget.style.background=isSelected?"#00d4ff06":"transparent")}
    >
      <div>
        <div style={{ fontWeight:500, fontSize:13 }}>{doc.doc_name}</div>
        <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>v{doc.version_number} · {doc.filename}</div>
      </div>
      <div style={{ fontFamily:T.mono, fontSize:9, color:"#7dd3fc" }}>{doc.doc_category}</div>
      <div><RatingChip rating={doc.overall_rating} size="sm"/></div>
      <div style={{ fontFamily:T.mono, fontSize:12, fontWeight:600, color:RATING_COLOR[doc.overall_rating]||T.muted, textAlign:"center" }}>{fmt(doc.overall_score)}</div>
      <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted, textAlign:"center" }}>{doc.section_count}</div>
      <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>{fmtDate(doc.analysed_at)}</div>
      <div style={{ display:"flex", gap:6 }} onClick={e=>e.stopPropagation()}>
        <Btn size="xs" onClick={onAnalyse} disabled={isAnalysing || doc.analyse_status==="pending"}>
          {isAnalysing ? "⟳" : "↺"} {isAnalysing ? "Running…" : "Analyse"}
        </Btn>
        <Btn size="xs" variant="danger" onClick={onDelete} title="Delete result">✕</Btn>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ComplexityPage({ user }) {
  const [docs,      setDocs]      = useState([]);
  const [stats,     setStats]     = useState(null);
  const [selected,  setSelected]  = useState(null);   // full result object
  const [loading,   setLoading]   = useState(true);
  const [analysing, setAnalysing] = useState(null);   // version_id being analysed
  const [expanded,  setExpanded]  = useState({});     // section_id → bool
  const [allDocs,   setAllDocs]   = useState([]);     // all documents for picker

  const loadList = useCallback(async () => {
    try {
      const [list, st, docs] = await Promise.all([
        apiGet("/complexity/list"),
        apiGet("/complexity/stats"),
        apiGet("/docs"),
      ]);
      setDocs(list);
      setStats(st);
      setAllDocs(docs);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  // Poll for pending analyses
  useEffect(() => {
    const pending = docs.filter(d => d.analyse_status === "pending");
    if (pending.length === 0) return;
    const i = setInterval(async () => {
      await loadList();
      if (selected && pending.find(p => p.version_id === selected.version_id)) {
        try {
          const fresh = await apiGet(`/complexity/result/${selected.version_id}`);
          setSelected(fresh);
        } catch(_) {}
      }
    }, 4000);
    return () => clearInterval(i);
  }, [docs, selected, loadList]);

  async function handleAnalyse(versionId) {
    setAnalysing(versionId);
    try {
      await apiPost(`/complexity/analyse/${versionId}`);
      await loadList();
    } catch(e) { alert(e.message); }
    finally { setAnalysing(null); }
  }

  async function handleSelect(versionId) {
    if (selected?.version_id === versionId) { setSelected(null); return; }
    try {
      const result = await apiGet(`/complexity/result/${versionId}`);
      setSelected(result);
      setExpanded({});
    } catch(e) {
      if (e.message.includes("404")) {
        alert("No analysis yet — click Analyse to run it first.");
      } else {
        alert(e.message);
      }
    }
  }

  async function handleDelete(versionId) {
    if (!confirm("Delete this complexity analysis?")) return;
    try {
      await apiDel(`/complexity/${versionId}`);
      if (selected?.version_id === versionId) setSelected(null);
      await loadList();
    } catch(e) { alert(e.message); }
  }

  const analysedVersionIds = new Set(docs.map(d => d.version_id));
  const unanalysed = allDocs.flatMap(d => {
    if (!["Requirements","Design"].includes(d.category)) return [];
    const versions = d.versions || [];
    // Only suggest the latest version per document (is_latest flag, or highest version_number)
    const latest = versions.find(v => v.is_latest) ||
      versions.reduce((a, b) => (!a || b.version_number > a.version_number ? b : a), null);
    if (!latest || analysedVersionIds.has(latest.id)) return [];
    return [{ ...latest, doc_name: d.name, doc_category: d.category, doc_id: d.id }];
  });

  const toggleSection = (id) => setExpanded(e => ({ ...e, [id]: !e[id] }));

  return (
    <>
      <style>{`@keyframes spin { to { transform:rotate(360deg); } } .spin { animation: spin 1.2s linear infinite; display:inline-block; }`}</style>

      {/* Page header */}
      <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", marginBottom:24, paddingBottom:16, borderBottom:`1px solid ${T.border}` }}>
        <div>
          <div style={{ fontFamily:T.mono, fontSize:18, fontWeight:500, letterSpacing:1 }}>COMPLEXITY ANALYSER</div>
          <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, marginTop:4 }}>
            Mistral-powered section-level complexity scoring · Requirements &amp; Design documents
          </div>
        </div>
        <Btn variant="ghost" size="sm" onClick={loadList}>⟳ Refresh</Btn>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 260px", gap:20, alignItems:"start" }}>
        <div>
          {/* Unanalysed docs quick-trigger */}
          {unanalysed.length > 0 && (
            <Panel style={{ marginBottom:16 }}>
              <PanelHdr>
                <PanelTitle color={T.orange}>Unanalysed Documents</PanelTitle>
                <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>{unanalysed.length} version(s) ready</span>
              </PanelHdr>
              <div style={{ padding:12, display:"flex", flexWrap:"wrap", gap:8 }}>
                {unanalysed.map(v => (
                  <div key={v.id} style={{ display:"flex", alignItems:"center", gap:8, padding:"6px 10px", background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3 }}>
                    <span style={{ fontFamily:T.mono, fontSize:10, color:T.text }}>{v.doc_name}</span>
                    <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>v{v.version_number}</span>
                    <Btn size="xs" onClick={()=>handleAnalyse(v.id)} disabled={analysing===v.id}>
                      {analysing===v.id ? <span className="spin">⟳</span> : "▶"} Analyse
                    </Btn>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {/* Analysed documents list */}
          <Panel style={{ marginBottom: selected ? 16 : 0 }}>
            <PanelHdr>
              <PanelTitle>Analysed Documents</PanelTitle>
              <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>Click row to drill down</span>
            </PanelHdr>

            <div style={{ display:"grid", gridTemplateColumns:"2fr 110px 100px 80px 80px 120px 120px", gap:0, padding:"8px 16px", borderBottom:`1px solid ${T.border}` }}>
              {["Document","Category","Rating","Score","Sections","Analysed",""].map((h,i)=>(
                <span key={i} style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", textTransform:"uppercase", color:T.muted }}>{h}</span>
              ))}
            </div>

            {loading
              ? <div style={{ padding:40, textAlign:"center", fontFamily:T.mono, color:T.muted }}>Loading…</div>
              : docs.length === 0
                ? <div style={{ padding:40, textAlign:"center", fontFamily:T.mono, color:T.muted }}>
                    No analyses yet. Upload a Requirements or Design document, then click Analyse.
                  </div>
                : docs.map(doc => (
                    <DocRow
                      key={doc.version_id}
                      doc={doc}
                      isSelected={selected?.version_id === doc.version_id}
                      onSelect={() => handleSelect(doc.version_id)}
                      onAnalyse={() => handleAnalyse(doc.version_id)}
                      onDelete={() => handleDelete(doc.version_id)}
                      analysing={analysing}
                    />
                  ))
            }
          </Panel>

          {/* Drill-down: section table */}
          {selected && (
            <Panel>
              <PanelHdr>
                <div>
                  <PanelTitle>{selected.doc_name} // v{selected.version_number}</PanelTitle>
                  <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted, marginTop:4 }}>
                    {selected.section_count} sections · avg score {fmt(selected.overall_score)} ·{" "}
                    <span style={{ color:RATING_COLOR[selected.overall_rating] }}>{RATING_ICON[selected.overall_rating]} {selected.overall_rating} overall</span>
                  </div>
                </div>
                <Btn variant="ghost" size="xs" onClick={()=>setSelected(null)}>× Close</Btn>
              </PanelHdr>

              <div style={{ display:"grid", gridTemplateColumns:"60px 2fr 130px 70px 110px 160px 28px", gap:0, padding:"8px 16px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
                {["ID","Title","Rating","Score","Confidence","Factors",""].map((h,i)=>(
                  <span key={i} style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", textTransform:"uppercase", color:T.muted }}>{h}</span>
                ))}
              </div>

              {selected.sections.length === 0
                ? <div style={{ padding:40, textAlign:"center", fontFamily:T.mono, color:T.muted }}>
                    {selected.analyse_status === "pending"
                      ? "⟳ Analysis in progress — please wait…"
                      : selected.analyse_status === "failed"
                        ? `Analysis failed: ${selected.error_message || "Unknown error"}`
                        : "No sections detected in this document."}
                  </div>
                : selected.sections.map(sec => (
                    <SectionRow
                      key={sec.id}
                      section={sec}
                      isExpanded={!!expanded[sec.id]}
                      onToggle={() => toggleSection(sec.id)}
                    />
                  ))
              }

              {/* Factor summary bar */}
              {Object.keys(selected.factor_summary || {}).length > 0 && (
                <div style={{ padding:14, borderTop:`1px solid ${T.border}`, background:T.surface, display:"flex", gap:10, flexWrap:"wrap" }}>
                  <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted, textTransform:"uppercase", letterSpacing:1, alignSelf:"center" }}>Factor categories:</span>
                  {Object.entries(selected.factor_summary).sort((a,b)=>b[1]-a[1]).map(([cat, count])=>(
                    <span key={cat} style={{ fontFamily:T.mono, fontSize:9, color:CAT_COLORS[cat]||T.muted, background:(CAT_COLORS[cat]||"#cbd5e1")+"18", border:`1px solid ${(CAT_COLORS[cat]||"#cbd5e1")}44`, padding:"2px 8px", borderRadius:2 }}>
                      {cat} ({count})
                    </span>
                  ))}
                </div>
              )}
            </Panel>
          )}
        </div>

        {/* Stats sidebar */}
        <div>
          <StatsPanel stats={stats}/>

          {/* Legend */}
          <Panel style={{ marginTop:14 }}>
            <PanelHdr><PanelTitle>Complexity Scale</PanelTitle></PanelHdr>
            <div style={{ padding:14, display:"flex", flexDirection:"column", gap:10 }}>
              {[
                { r:"Simple",   desc:"0-2 factors · Junior-capable · No design review" },
                { r:"Moderate", desc:"3-4 factors · Experienced dev · Design review recommended" },
                { r:"Complex",  desc:"5-6 factors · Senior required · Spike/POC before estimate" },
                { r:"Critical", desc:"7+ factors · Architect review mandatory · High estimation risk" },
              ].map(({ r, desc }) => (
                <div key={r} style={{ display:"flex", flexDirection:"column", gap:4 }}>
                  <RatingChip rating={r} size="sm"/>
                  <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted, lineHeight:1.5 }}>{desc}</div>
                </div>
              ))}
            </div>
          </Panel>

          {/* Weight legend */}
          <Panel style={{ marginTop:14 }}>
            <PanelHdr><PanelTitle>Factor Weights</PanelTitle></PanelHdr>
            <div style={{ padding:14, display:"flex", flexDirection:"column", gap:8 }}>
              {[1,2,3].map(w => (
                <div key={w} style={{ display:"flex", alignItems:"center", gap:8 }}>
                  <span style={{ fontFamily:T.mono, fontSize:10, color:WEIGHT_COLOR[w], minWidth:80 }}>{"●".repeat(w)} {WEIGHT_LABEL[w]}</span>
                  <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>
                    {w===1?"Low implementation overhead":w===2?"Significant design consideration":"High risk, architect input needed"}
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
