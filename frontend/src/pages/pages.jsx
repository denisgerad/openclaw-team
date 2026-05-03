/**
 * All remaining pages in one file for project clarity.
 * Split into individual files as the project scales.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { getTeamStatus, getEngineStatus, triggerWorker, getNotes, createNote, updateNote, deleteNote, getFiles, queueDownload, getActiveSprint, getSprintTasks, createSprintTask, updateSprintTask, deleteSprintTask } from "../api";
import { T, RISK_META, RiskChip, SprintBadge, IssueStatusBadge, Btn, Modal, Field, Input, Select, Textarea } from "../components/Sidebar";
import { useAuth } from "../AuthContext";

// ── HELPERS ───────────────────────────────────────────────────────────────────

function Section({ title, sub, children, action }) {
  return (
    <>
      <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", marginBottom:24, paddingBottom:16, borderBottom:`1px solid ${T.border}` }}>
        <div>
          <div style={{ fontFamily:T.mono, fontSize:18, fontWeight:500, letterSpacing:1 }}>{title}</div>
          {sub && <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, marginTop:4 }}>{sub}</div>}
        </div>
        {action}
      </div>
      {children}
    </>
  );
}

function Panel({ children, style={} }) {
  return <div style={{ background:T.panel, border:`1px solid ${T.border}`, borderRadius:4, overflow:"hidden", ...style }}>{children}</div>;
}

function PanelHeader({ children }) {
  return <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"12px 16px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>{children}</div>;
}

function PanelTitle({ children }) {
  return <span style={{ fontFamily:T.mono, fontSize:11, letterSpacing:2, color:T.accent, textTransform:"uppercase" }}>{children}</span>;
}


// ─────────────────────────────────────────────────────────────────────────────
// TEAM SUMMARY
// ─────────────────────────────────────────────────────────────────────────────

export function TeamSummary() {
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTeamStatus().then(setMembers).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ fontFamily:T.mono, color:T.muted, padding:40 }}>Loading…</div>;

  return (
    <Section title="TEAM SUMMARY // GLOBAL VIEW" sub={`Sprint · ${members.length} members`}>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:14 }}>
        {members.map(m => {
          const rm = RISK_META[m.risk_level_confirmed || m.risk_level] || RISK_META.None;
          return (
            <Panel key={m.user_id} style={{ borderTop:`2px solid ${rm.dot}` }}>
              <div style={{ padding:"14px 16px" }}>
                <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:10 }}>
                  <div>
                    <div style={{ fontWeight:500, fontSize:13 }}>{m.user_name}</div>
                    <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>{m.user_team_role}</div>
                  </div>
                  <div style={{ width:32, height:32, borderRadius:"50%", background:rm.dot + "44", border:`1px solid ${rm.dot}`, display:"flex", alignItems:"center", justifyContent:"center", fontFamily:T.mono, fontSize:11, color:rm.dot, fontWeight:600 }}>
                    {m.user_name.split(" ").map(w=>w[0]).join("").slice(0,2)}
                  </div>
                </div>
                <div style={{ display:"flex", flexDirection:"column", gap:7 }}>
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
                    <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted, textTransform:"uppercase", letterSpacing:1 }}>Risk</span>
                    <RiskChip level={m.risk_level_confirmed || m.risk_level}/>
                  </div>
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
                    <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted, textTransform:"uppercase", letterSpacing:1 }}>Sprint</span>
                    <SprintBadge status={m.sprint_status}/>
                  </div>
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
                    <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted, textTransform:"uppercase", letterSpacing:1 }}>Issue</span>
                    <IssueStatusBadge status={m.issue_status}/>
                  </div>
                  {m.risk_detail && <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted, marginTop:4, lineHeight:1.5, borderTop:`1px solid ${T.border}`, paddingTop:8 }}>{m.risk_detail}</div>}
                  <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>{new Date(m.updated_at).toLocaleString("en-GB",{hour12:false,hour:"2-digit",minute:"2-digit",day:"2-digit",month:"short"})}</div>
                </div>
              </div>
            </Panel>
          );
        })}
      </div>
    </Section>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// ENGINE CONTROL
// ─────────────────────────────────────────────────────────────────────────────

const WORKER_META = {
  risk_classifier:   { label:"Risk Classifier",   color:"#7dd3fc", schedule:"Every 5 min",  startup:true  },
  digest_generator:  { label:"Digest Generator",  color:"#86efac", schedule:"Daily 08:00",  startup:false },
  reminder_engine:   { label:"Reminder Engine",   color:"#fcd34d", schedule:"Every 1 hr",   startup:true  },
  workflow_triggers: { label:"Workflow Triggers", color:"#c4b5fd", schedule:"Every 2 min",  startup:true  },
};

export function EngineControl() {
  const [workers, setWorkers]     = useState({});
  const [log, setLog]             = useState([]);
  const [triggering, setTriggering] = useState(null);
  const [loading, setLoading]     = useState(true);

  const addLog = useCallback((worker, msg) => {
    const time = new Date().toLocaleTimeString("en-GB", { hour12:false, hour:"2-digit", minute:"2-digit", second:"2-digit" });
    setLog(l => [...l.slice(-19), { time, worker, msg }]);
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getEngineStatus();
      setWorkers(data);
    } catch (e) {
      addLog("system", `Status fetch error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [addLog]);

  useEffect(() => { fetchStatus(); const i = setInterval(fetchStatus, 15000); return () => clearInterval(i); }, [fetchStatus]);

  async function handleTrigger(name) {
    setTriggering(name);
    addLog(name, `Manual trigger → POST /api/engine/trigger/${name}`);
    try {
      const res = await triggerWorker(name);
      addLog(name, `Completed — run #${res.state?.run_count}`);
      await fetchStatus();
    } catch (e) {
      addLog(name, `Error: ${e.message}`);
    } finally {
      setTriggering(null);
    }
  }

  const healthy  = Object.values(workers).filter(w=>w.healthy).length;
  const total    = Object.keys(workers).length;
  const errored  = Object.values(workers).filter(w=>w.status==="error").length;
  const totalRuns= Object.values(workers).reduce((a,w)=>a+(w.run_count||0),0);

  return (
    <Section title="ENGINE CONTROL" sub="APScheduler · 4 modular workers"
      action={<Btn variant="ghost" size="sm" onClick={fetchStatus}>⟳ Refresh</Btn>}>

      {/* Summary bar */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:24 }}>
        {[
          { label:"Healthy",    value:`${healthy}/${total}`, color:T.green  },
          { label:"Running",    value:Object.values(workers).filter(w=>w.is_running).length, color:T.accent },
          { label:"Errors",     value:errored, color:errored>0?T.red:T.green },
          { label:"Total Runs", value:totalRuns, color:T.accent },
        ].map(c => (
          <Panel key={c.label}>
            <div style={{ padding:"12px 14px" }}>
              <div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", color:T.muted, textTransform:"uppercase", marginBottom:6 }}>{c.label}</div>
              <div style={{ fontFamily:T.mono, fontSize:22, fontWeight:600, color:c.color }}>{c.value}</div>
            </div>
          </Panel>
        ))}
      </div>

      {/* Worker cards */}
      {loading
        ? <div style={{ fontFamily:T.mono, color:T.muted, padding:40 }}>Loading worker status…</div>
        : (
          <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:14, marginBottom:24 }}>
            {Object.entries(workers).map(([name, ws]) => {
              const meta = WORKER_META[name] || { label:name, color:T.muted, schedule:"—", startup:false };
              const dotColor = ws.status==="error" ? T.red : ws.is_running ? T.accent : ws.healthy ? T.green : T.muted;
              const isTriggering = triggering === name;
              return (
                <Panel key={name}>
                  <div style={{ display:"flex", alignItems:"center", gap:10, padding:"12px 14px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
                    <div style={{ width:8, height:8, borderRadius:"50%", background:dotColor, boxShadow:`0 0 6px ${dotColor}` }} />
                    <span style={{ fontFamily:T.mono, fontSize:11, fontWeight:600, letterSpacing:1, color:meta.color }}>{meta.label}</span>
                    <span style={{ marginLeft:"auto", fontFamily:T.mono, fontSize:9, color:T.muted, background:"#ffffff08", padding:"2px 6px", borderRadius:2 }}>{ws.status?.toUpperCase()}</span>
                  </div>
                  <div style={{ padding:"12px 14px" }}>
                    <div style={{ fontSize:11, color:T.muted, lineHeight:1.5, marginBottom:10 }}>{ws.description}</div>
                    <div style={{ display:"flex", flexWrap:"wrap", gap:10, marginBottom:10 }}>
                      {[
                        ["Schedule", meta.schedule],
                        ["Startup", meta.startup ? "YES" : "NO"],
                        ["Last run", ws.last_run ? new Date(ws.last_run).toLocaleTimeString("en-GB") : "—"],
                        ["Next run", ws.next_run ? new Date(ws.next_run).toLocaleTimeString("en-GB") : "—"],
                      ].map(([k,v]) => (
                        <div key={k} style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>
                          {k}: <span style={{ color: k==="Startup" && v==="YES" ? T.green : T.text }}>{v}</span>
                        </div>
                      ))}
                    </div>
                    {ws.last_error && <div style={{ fontFamily:T.mono, fontSize:9, color:T.red, marginBottom:8 }}>Error: {ws.last_error}</div>}
                  </div>
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"10px 14px", borderTop:`1px solid ${T.border}` }}>
                    <span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>Run #{ws.run_count}</span>
                    <Btn size="xs" disabled={isTriggering || ws.is_running} onClick={() => handleTrigger(name)}>
                      {isTriggering ? "Running…" : "▶ Trigger Now"}
                    </Btn>
                  </div>
                </Panel>
              );
            })}
          </div>
        )
      }

      {/* Activity log */}
      <Panel>
        <PanelHeader><PanelTitle>Engine Activity Log</PanelTitle><span style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>Latest 20 entries</span></PanelHeader>
        <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, padding:"12px 14px", maxHeight:200, overflowY:"auto", display:"flex", flexDirection:"column", gap:4 }}>
          {log.length === 0
            ? <span>No activity yet — trigger a worker to see output.</span>
            : [...log].reverse().map((e, i) => (
              <div key={i} style={{ display:"flex", gap:12, lineHeight:1.4 }}>
                <span style={{ color:T.muted, flexShrink:0 }}>{e.time}</span>
                <span style={{ flexShrink:0, color: WORKER_META[e.worker]?.color || T.accent }}>[{e.worker}]</span>
                <span style={{ color:T.text }}>{e.msg}</span>
              </div>
            ))
          }
        </div>
      </Panel>
    </Section>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// NOTES
// ─────────────────────────────────────────────────────────────────────────────

export function NotesPage() {
  const [notes, setNotes]   = useState([]);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm]     = useState({ title:"", content:"", tags:"", pinned:false });
  const setF = (k,v) => setForm(p=>({...p,[k]:v}));

  const load = () => getNotes().then(setNotes).catch(console.error);
  useEffect(() => { load(); }, []);

  async function handleSave() {
    try {
      if (editing) { await updateNote(editing.id, form); }
      else         { await createNote(form); }
      await load();
      setAdding(false);
      setEditing(null);
      setForm({ title:"", content:"", tags:"", pinned:false });
    } catch (e) { alert(e.message); }
  }

  function openEdit(note) {
    setForm({ title:note.title, content:note.content, tags:note.tags, pinned:note.pinned });
    setEditing(note);
  }

  async function handleDelete(id) {
    if (!confirm("Delete this note?")) return;
    await deleteNote(id);
    await load();
  }

  const NoteForm = () => (
    <Modal title={editing ? "Edit Note" : "New Note"} onClose={()=>{setAdding(false);setEditing(null);}}
      footer={<><Btn variant="ghost" onClick={()=>{setAdding(false);setEditing(null);}}>Cancel</Btn><Btn onClick={handleSave}>Save</Btn></>}>
      <Field label="Title"><Input value={form.title} onChange={e=>setF("title",e.target.value)} placeholder="Note title"/></Field>
      <Field label="Content"><Textarea rows={6} value={form.content} onChange={e=>setF("content",e.target.value)} placeholder="Write your note…"/></Field>
      <Field label="Tags (comma-separated)"><Input value={form.tags} onChange={e=>setF("tags",e.target.value)} placeholder="#urgent, #sprint, #blocker"/></Field>
    </Modal>
  );

  return (
    <Section title="NOTES" sub="Personal notes — tag #urgent to alert manager"
      action={<Btn size="sm" onClick={()=>{ setForm({title:"",content:"",tags:"",pinned:false}); setAdding(true); }}>+ New Note</Btn>}>
      {notes.length === 0
        ? <div style={{ fontFamily:T.mono, color:T.muted, padding:40, textAlign:"center" }}>No notes yet. Click + New Note to get started.</div>
        : <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12 }}>
            {notes.map(n => (
              <Panel key={n.id}>
                <div style={{ padding:"14px 16px" }}>
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:8 }}>
                    <div style={{ fontWeight:500, fontSize:13 }}>{n.pinned?"📌 ":""}{n.title}</div>
                  </div>
                  <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, lineHeight:1.6, marginBottom:10, whiteSpace:"pre-wrap" }}>{n.content.slice(0,200)}{n.content.length>200?"…":""}</div>
                  {n.tags && <div style={{ display:"flex", gap:6, flexWrap:"wrap", marginBottom:10 }}>{n.tags.split(",").map(t=><span key={t} style={{ fontFamily:T.mono, fontSize:9, color:T.accent, background:"#00d4ff12", border:`1px solid #00d4ff33`, padding:"1px 6px", borderRadius:2 }}>{t.trim()}</span>)}</div>}
                  <div style={{ display:"flex", gap:8 }}>
                    <Btn variant="ghost" size="xs" onClick={()=>openEdit(n)}>Edit</Btn>
                    <Btn variant="danger" size="xs" onClick={()=>handleDelete(n.id)}>Delete</Btn>
                  </div>
                </div>
              </Panel>
            ))}
          </div>
      }
      {(adding || editing) && <NoteForm />}
    </Section>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// FILE MANAGER
// ─────────────────────────────────────────────────────────────────────────────

const STATUS_COLOR = { complete:"#00d68f", pending:"#ff8c00", downloading:"#00d4ff", failed:"#ff3b3b" };

export function FilesPage() {
  const [files, setFiles]   = useState([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm]     = useState({ source_url:"", filename:"" });

  const load = () => getFiles().then(setFiles).catch(console.error);
  useEffect(() => { load(); const i = setInterval(load, 5000); return () => clearInterval(i); }, []);

  async function handleQueue() {
    try {
      await queueDownload(form);
      setForm({ source_url:"", filename:"" });
      setAdding(false);
      await load();
    } catch (e) { alert(e.message); }
  }

  return (
    <Section title="FILE MANAGER" sub="URL-based async downloader · Auto-refreshes every 5s"
      action={<Btn size="sm" onClick={()=>setAdding(true)}>+ Queue Download</Btn>}>
      <Panel>
        <PanelHeader><PanelTitle>Downloads</PanelTitle></PanelHeader>
        {files.length === 0
          ? <div style={{ padding:40, textAlign:"center", fontFamily:T.mono, color:T.muted }}>No files yet. Queue a download to get started.</div>
          : <table style={{ width:"100%", borderCollapse:"collapse" }}>
              <thead><tr>
                {["Filename","Source URL","Size","Status","Queued","Completed"].map(h=>
                  <th key={h} style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", textTransform:"uppercase", color:T.muted, padding:"10px 14px", textAlign:"left", borderBottom:`1px solid ${T.border}` }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {files.map(f => (
                  <tr key={f.id} style={{ borderBottom:`1px solid ${T.border}` }}>
                    <td style={{ padding:"11px 14px", fontFamily:T.mono, fontSize:11 }}>{f.filename}</td>
                    <td style={{ padding:"11px 14px", fontFamily:T.mono, fontSize:10, color:T.muted, maxWidth:200 }}>{f.source_url.slice(0,50)}…</td>
                    <td style={{ padding:"11px 14px", fontFamily:T.mono, fontSize:11 }}>{f.size_bytes > 0 ? `${(f.size_bytes/1024).toFixed(1)} KB` : "—"}</td>
                    <td style={{ padding:"11px 14px" }}><span style={{ fontFamily:T.mono, fontSize:10, fontWeight:500, color:STATUS_COLOR[f.download_status]||T.muted }}>{f.download_status}</span></td>
                    <td style={{ padding:"11px 14px", fontFamily:T.mono, fontSize:10, color:T.muted }}>{new Date(f.created_at).toLocaleString("en-GB",{hour12:false,hour:"2-digit",minute:"2-digit",day:"2-digit",month:"short"})}</td>
                    <td style={{ padding:"11px 14px", fontFamily:T.mono, fontSize:10, color:T.muted }}>{f.completed_at ? new Date(f.completed_at).toLocaleString("en-GB",{hour12:false,hour:"2-digit",minute:"2-digit",day:"2-digit",month:"short"}) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
        }
      </Panel>

      {adding && (
        <Modal title="Queue Download" onClose={()=>setAdding(false)}
          footer={<><Btn variant="ghost" onClick={()=>setAdding(false)}>Cancel</Btn><Btn onClick={handleQueue}>Queue</Btn></>}>
          <Field label="Source URL"><Input value={form.source_url} onChange={e=>setForm(p=>({...p,source_url:e.target.value}))} placeholder="https://example.com/file.pdf"/></Field>
          <Field label="Filename (optional)"><Input value={form.filename} onChange={e=>setForm(p=>({...p,filename:e.target.value}))} placeholder="my-file.pdf"/></Field>
        </Modal>
      )}
    </Section>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
// LOGIN PAGE
// ─────────────────────────────────────────────────────────────────────────────

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail]     = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]     = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight:"100vh", background:T.bg, display:"flex", alignItems:"center", justifyContent:"center", backgroundImage:"radial-gradient(ellipse 60% 40% at 50% 0%, #001a2c55 0%, transparent 60%)" }}>
      <div style={{ background:T.panel, border:`1px solid ${T.border2}`, borderRadius:6, padding:40, width:400 }}>
        <div style={{ fontFamily:T.mono, fontSize:18, fontWeight:600, letterSpacing:3, color:T.accent, textTransform:"uppercase", marginBottom:4 }}>
          Open<span style={{ color:T.muted, fontWeight:300 }}>Claw</span>
        </div>
        <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted, marginBottom:32, letterSpacing:2 }}>TEAM PLATFORM // SIGN IN</div>

        <form onSubmit={handleLogin}>
          <Field label="Email">
            <Input type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@team.com" required />
          </Field>
          <Field label="Password">
            <Input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="••••••••" required />
          </Field>
          {error && <div style={{ fontFamily:T.mono, fontSize:11, color:T.red, marginBottom:14 }}>{error}</div>}
          <button type="submit" disabled={loading} style={{ width:"100%", padding:"10px 0", background:"transparent", border:`1px solid ${T.accent}`, borderRadius:3, color:T.accent, fontFamily:T.mono, fontSize:12, fontWeight:500, cursor:loading?"not-allowed":"pointer", letterSpacing:1, opacity:loading?0.5:1 }}>
            {loading ? "Signing in…" : "Sign In →"}
          </button>
        </form>

        <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted, marginTop:20, lineHeight:1.8, borderTop:`1px solid ${T.border}`, paddingTop:16 }}>
          New team members: ask your manager to register your account<br/>
          via POST /api/auth/register
        </div>
      </div>
    </div>
  );
}

export default LoginPage;


// ─────────────────────────────────────────────────────────────────────────────
// CALENDAR PAGE  — sprint task board + timeline
// ─────────────────────────────────────────────────────────────────────────────

const TASK_STATUS_META = {
  todo:        { color: T.muted,   label: "To Do",       icon: "○" },
  in_progress: { color: T.accent,  label: "In Progress", icon: "◉" },
  done:        { color: T.green,   label: "Done",        icon: "✓" },
  blocked:     { color: T.red,     label: "Blocked",     icon: "✕" },
};

const PRIORITY_META = {
  low:      { color: T.muted,   label: "Low"      },
  normal:   { color: T.text,    label: "Normal"   },
  high:     { color: T.orange,  label: "High"     },
  critical: { color: T.red,     label: "Critical" },
};

const TASK_STATUSES  = ["todo", "in_progress", "done", "blocked"];
const TASK_PRIORITIES = ["low", "normal", "high", "critical"];

function PriorityDot({ priority }) {
  const m = PRIORITY_META[priority] || PRIORITY_META.normal;
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:4, fontFamily:T.mono, fontSize:9, color:m.color }}>
      <span style={{ width:6, height:6, borderRadius:"50%", background:m.color, flexShrink:0 }} />
      {m.label}
    </span>
  );
}

function TaskModal({ task, onSave, onClose, user }) {
  const empty = { title:"", description:"", status:"todo", priority:"normal", due_date:"", user_id: user.id };
  const [form, setForm] = useState(task ? {
    title:       task.title,
    description: task.description,
    status:      task.status,
    priority:    task.priority,
    due_date:    task.due_date ? task.due_date.slice(0,10) : "",
    user_id:     task.user_id ?? user.id,
  } : empty);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <Modal title={task ? "Edit Task" : "New Task"} onClose={onClose}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancel</Btn><Btn onClick={() => onSave(form)}>Save</Btn></>}>
      <Field label="Title">
        <Input value={form.title} onChange={e=>set("title",e.target.value)} placeholder="Task title…" />
      </Field>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
        <Field label="Status">
          <Select value={form.status} onChange={e=>set("status",e.target.value)}>
            {TASK_STATUSES.map(s => <option key={s} value={s}>{TASK_STATUS_META[s]?.label || s}</option>)}
          </Select>
        </Field>
        <Field label="Priority">
          <Select value={form.priority} onChange={e=>set("priority",e.target.value)}>
            {TASK_PRIORITIES.map(p => <option key={p} value={p}>{PRIORITY_META[p]?.label || p}</option>)}
          </Select>
        </Field>
      </div>
      <Field label="Due Date">
        <Input type="date" value={form.due_date} onChange={e=>set("due_date",e.target.value)} />
      </Field>
      <Field label="Description">
        <Textarea value={form.description} onChange={e=>set("description",e.target.value)} placeholder="Optional details…" />
      </Field>
    </Modal>
  );
}

export function CalendarPage({ user }) {
  const [sprint,  setSprint]  = useState(null);
  const [tasks,   setTasks]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding,  setAdding]  = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    try {
      const [sprintData, taskData] = await Promise.all([getActiveSprint(), getSprintTasks()]);
      setSprint(sprintData);
      setTasks(taskData || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleSave(form) {
    const payload = {
      ...form,
      due_date: form.due_date ? new Date(form.due_date + "T23:59:00Z").toISOString() : null,
      user_id:  form.user_id || null,
    };
    try {
      if (editing) { await updateSprintTask(editing.id, payload); }
      else         { await createSprintTask(payload); }
      await load();
      setAdding(false);
      setEditing(null);
    } catch (e) { alert(e.message); }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this task?")) return;
    try { await deleteSprintTask(id); await load(); } catch (e) { alert(e.message); }
  }

  // Group tasks by status column
  const columns = TASK_STATUSES.map(s => ({
    key:   s,
    meta:  TASK_STATUS_META[s],
    tasks: tasks.filter(t => t.status === s),
  }));

  const now      = new Date();
  const sprintEnd = sprint ? new Date(sprint.end_date) : null;
  const daysLeft  = sprintEnd ? Math.ceil((sprintEnd - now) / 86400000) : null;

  return (
    <Section
      title="CALENDAR // SPRINT BOARD"
      sub={sprint ? `${sprint.name} · ${new Date(sprint.start_date).toLocaleDateString("en-GB")} → ${sprintEnd.toLocaleDateString("en-GB")}` : "No active sprint"}
      action={<Btn size="sm" onClick={() => setAdding(true)}>+ New Task</Btn>}
    >
      {/* Sprint status bar */}
      {sprint && (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:24 }}>
          {[
            { label:"Sprint",    value:sprint.name,                      color:T.accent  },
            { label:"Days Left", value:daysLeft !== null ? `${daysLeft}d` : "—", color:daysLeft <= 2 ? T.red : T.green },
            { label:"Total",     value:tasks.length,                     color:T.text    },
            { label:"Done",      value:tasks.filter(t=>t.status==="done").length, color:T.green },
          ].map(c => (
            <div key={c.label} style={{ background:T.panel, border:`1px solid ${T.border}`, borderRadius:4, padding:"12px 16px", position:"relative", overflow:"hidden" }}>
              <div style={{ position:"absolute", top:0, left:0, right:0, height:2, background:c.color }} />
              <div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:2, color:T.muted, textTransform:"uppercase", marginBottom:6 }}>{c.label}</div>
              <div style={{ fontFamily:T.mono, fontSize:22, fontWeight:600, color:c.color }}>{c.value}</div>
            </div>
          ))}
        </div>
      )}

      {loading && <div style={{ fontFamily:T.mono, color:T.muted, padding:40 }}>Loading…</div>}

      {!loading && (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:14 }}>
          {columns.map(col => (
            <div key={col.key}>
              {/* Column header */}
              <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:10, padding:"8px 12px", background:T.surface, border:`1px solid ${T.border}`, borderRadius:4 }}>
                <span style={{ color:col.meta.color, fontSize:14 }}>{col.meta.icon}</span>
                <span style={{ fontFamily:T.mono, fontSize:10, fontWeight:600, letterSpacing:1, color:col.meta.color, textTransform:"uppercase" }}>{col.meta.label}</span>
                <span style={{ marginLeft:"auto", fontFamily:T.mono, fontSize:10, color:T.muted }}>{col.tasks.length}</span>
              </div>

              {/* Task cards */}
              <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
                {col.tasks.length === 0 && (
                  <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted, padding:"14px 12px", background:T.panel, border:`1px dashed ${T.border}`, borderRadius:4, textAlign:"center" }}>—</div>
                )}
                {col.tasks.map(task => {
                  const overdue = task.due_date && new Date(task.due_date) < now && task.status !== "done";
                  return (
                    <div key={task.id} style={{ background:T.panel, border:`1px solid ${overdue ? T.red : T.border}`, borderRadius:4, padding:"12px 14px" }}>
                      <div style={{ fontWeight:500, fontSize:12, marginBottom:6, lineHeight:1.4 }}>{task.title}</div>
                      {task.description && (
                        <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted, marginBottom:8, lineHeight:1.5 }}>
                          {task.description.slice(0,80)}{task.description.length>80?"…":""}
                        </div>
                      )}
                      <div style={{ display:"flex", flexWrap:"wrap", gap:6, marginBottom:8 }}>
                        <PriorityDot priority={task.priority} />
                        {task.due_date && (
                          <span style={{ fontFamily:T.mono, fontSize:9, color:overdue?T.red:T.muted }}>
                            {overdue?"⚠ ":""}Due {new Date(task.due_date).toLocaleDateString("en-GB")}
                          </span>
                        )}
                      </div>
                      {task.user_name && (
                        <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted, marginBottom:8 }}>
                          Assignee: {task.user_name}
                        </div>
                      )}
                      <div style={{ display:"flex", gap:6 }}>
                        <Btn variant="ghost" size="xs" onClick={() => setEditing(task)}>Edit</Btn>
                        {user.role === "manager" && (
                          <Btn variant="danger" size="xs" onClick={() => handleDelete(task.id)}>Del</Btn>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {(adding || editing) && (
        <TaskModal
          task={editing}
          user={user}
          onSave={handleSave}
          onClose={() => { setAdding(false); setEditing(null); }}
        />
      )}
    </Section>
  );
}
