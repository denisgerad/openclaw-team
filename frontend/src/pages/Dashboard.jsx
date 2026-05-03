import { useState, useEffect, useCallback } from "react";
import { getTeamStatus, postStatus } from "../api";
import { T, RISK_META, RiskChip, SprintBadge, IssueStatusBadge, Btn, Modal, Field, Input, Select, Textarea } from "../components/Sidebar";

const RISK_LEVELS    = ["None","Minor","Moderate","Critical"];
const SPRINT_OPTIONS = ["On Time","At Risk","Delayed"];
const ISSUE_OPTIONS  = ["—","Bug fixes unresolved","Build issues","Dependency blocked","Test failures","Environment issue"];
const ISSUE_STATUSES = ["Resolved","In Progress","Open"];

function StatCard({ label, value, color, detail }) {
  return (
    <div style={{ background:T.panel, border:`1px solid ${T.border}`, borderRadius:4, padding:"14px 16px", position:"relative", overflow:"hidden" }}>
      <div style={{ position:"absolute", top:0, left:0, right:0, height:2, background:color }} />
      <div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:2, color:T.muted, textTransform:"uppercase", marginBottom:8 }}>{label}</div>
      <div style={{ fontFamily:T.mono, fontSize:28, fontWeight:600, color }}>{value}</div>
      <div style={{ fontSize:10, color:T.muted, marginTop:4 }}>{detail}</div>
    </div>
  );
}

function UpdateModal({ member, onSave, onClose }) {
  const [form, setForm] = useState({
    risk_level:    member.risk_level_confirmed || member.risk_level,
    risk_detail:   member.risk_detail,
    sprint_status: member.sprint_status,
    issue:         member.issue,
    issue_status:  member.issue_status,
    comments:      member.comments,
  });
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <Modal title={`Update // ${member.user_name}`} onClose={onClose}
      footer={<><Btn variant="ghost" onClick={onClose}>Cancel</Btn><Btn onClick={() => onSave(form)}>Save Update</Btn></>}>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
        <Field label="Risk Level"><Select value={form.risk_level} onChange={e=>set("risk_level",e.target.value)}>{RISK_LEVELS.map(r=><option key={r}>{r}</option>)}</Select></Field>
        <Field label="Sprint Status"><Select value={form.sprint_status} onChange={e=>set("sprint_status",e.target.value)}>{SPRINT_OPTIONS.map(s=><option key={s}>{s}</option>)}</Select></Field>
      </div>
      <Field label="Risk Detail"><Input value={form.risk_detail} onChange={e=>set("risk_detail",e.target.value)} placeholder="e.g. Hardware not available, dependency blocked…"/></Field>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
        <Field label="Issue"><Select value={form.issue} onChange={e=>set("issue",e.target.value)}>{ISSUE_OPTIONS.map(o=><option key={o}>{o}</option>)}</Select></Field>
        <Field label="Issue Status"><Select value={form.issue_status} onChange={e=>set("issue_status",e.target.value)}>{ISSUE_STATUSES.map(s=><option key={s}>{s}</option>)}</Select></Field>
      </div>
      <Field label="Comments"><Textarea value={form.comments} onChange={e=>set("comments",e.target.value)} placeholder="Current status, blockers, notes…"/></Field>
    </Modal>
  );
}

export default function Dashboard({ user }) {
  const [members,  setMembers]  = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [selected, setSelected] = useState(null);
  const [editing,  setEditing]  = useState(null);
  const [saving,   setSaving]   = useState(false);

  const fetchTeam = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getTeamStatus();
      setMembers(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTeam(); }, [fetchTeam]);

  async function handleSave(form) {
    setSaving(true);
    try {
      await postStatus(form);
      await fetchTeam();
      setEditing(null);
    } catch (e) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  }

  const critical = members.filter(m => m.risk_level === "Critical").length;
  const delayed  = members.filter(m => m.sprint_status === "Delayed").length;
  const open     = members.filter(m => m.issue_status === "Open").length;
  const onTrack  = members.filter(m => m.sprint_status === "On Time").length;

  const sel = selected ? members.find(m => m.user_id === selected) : null;

  return (
    <>
      <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", marginBottom:24, paddingBottom:16, borderBottom:`1px solid ${T.border}` }}>
        <div>
          <div style={{ fontFamily:T.mono, fontSize:18, fontWeight:500, letterSpacing:1 }}>TEAM STATUS // SPRINT</div>
          <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, marginTop:4 }}>{members.length} members · {new Date().toLocaleDateString("en-GB")}</div>
        </div>
        <Btn variant="ghost" size="sm" onClick={fetchTeam}>⟳ Refresh</Btn>
      </div>

      {/* Stat cards */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:24 }}>
        <StatCard label="Critical Risk" value={critical} color={T.red}    detail="Immediate action" />
        <StatCard label="Delayed"       value={delayed}  color={T.orange} detail="Sprint behind" />
        <StatCard label="Open Issues"   value={open}     color={T.yellow} detail="Unresolved" />
        <StatCard label="On Track"      value={onTrack}  color={T.green}  detail="On time" />
      </div>

      {/* Selected member detail */}
      {sel && (
        <div style={{ background:T.panel, border:`1px solid ${T.border}`, borderRadius:4, overflow:"hidden", marginBottom:24 }}>
          <div style={{ display:"flex", alignItems:"center", gap:14, padding:"16px 20px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
            <div style={{ fontWeight:600, fontSize:14 }}>{sel.user_name}</div>
            <div style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>{sel.user_team_role}</div>
            <div style={{ marginLeft:"auto", display:"flex", gap:10 }}>
              {sel.user_id === user.id && <Btn size="sm" onClick={() => setEditing(sel)}>✎ Update My Status</Btn>}
              <Btn variant="ghost" size="sm" onClick={() => setSelected(null)}>× Close</Btn>
            </div>
          </div>
          <div style={{ padding:20, display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:16 }}>
            <div><div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", color:T.muted, textTransform:"uppercase", marginBottom:4 }}>Risk</div><RiskChip level={sel.risk_level_confirmed || sel.risk_level}/>{sel.risk_detail && <div style={{ fontFamily:T.mono, fontSize:11, color:T.muted, marginTop:4, lineHeight:1.5 }}>{sel.risk_detail}</div>}</div>
            <div><div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", color:T.muted, textTransform:"uppercase", marginBottom:4 }}>Sprint</div><SprintBadge status={sel.sprint_status}/></div>
            <div><div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", color:T.muted, textTransform:"uppercase", marginBottom:4 }}>Issue</div><span style={{ fontFamily:T.mono, fontSize:10, background:"#ffffff08", border:`1px solid ${T.border2}`, padding:"2px 7px", borderRadius:2 }}>{sel.issue}</span><div style={{ marginTop:4 }}><IssueStatusBadge status={sel.issue_status}/></div></div>
            <div style={{ gridColumn:"1/-1" }}><div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", color:T.muted, textTransform:"uppercase", marginBottom:4 }}>Comments</div><span style={{ fontFamily:T.mono, fontSize:12, color:T.muted, lineHeight:1.6 }}>{sel.comments || "—"}</span></div>
          </div>
        </div>
      )}

      {/* Table */}
      <div style={{ background:T.panel, border:`1px solid ${T.border}`, borderRadius:4, overflow:"hidden" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"12px 16px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
          <span style={{ fontFamily:T.mono, fontSize:11, letterSpacing:2, color:T.accent, textTransform:"uppercase" }}>Member Status Table</span>
          <span style={{ fontFamily:T.mono, fontSize:10, color:T.muted }}>Click row · Double-click to edit your status</span>
        </div>

        {loading && <div style={{ padding:40, textAlign:"center", fontFamily:T.mono, fontSize:12, color:T.muted }}>Loading…</div>}
        {error   && <div style={{ padding:20, color:T.red, fontFamily:T.mono, fontSize:12 }}>{error}</div>}

        {!loading && !error && (
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead>
              <tr>
                {["Member","Risk","Risk Detail","Issue","Issue Status","Sprint","Comments","Updated",""].map(h => (
                  <th key={h} style={{ fontFamily:T.mono, fontSize:9, letterSpacing:"1.5px", textTransform:"uppercase", color:T.muted, padding:"10px 14px", textAlign:"left", borderBottom:`1px solid ${T.border}`, whiteSpace:"nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {members.map(m => (
                <tr key={m.user_id}
                  style={{ borderBottom:`1px solid ${T.border}`, cursor:"pointer", background:selected===m.user_id?"#00d4ff06":"transparent" }}
                  onClick={() => setSelected(s => s===m.user_id ? null : m.user_id)}
                  onDoubleClick={() => m.user_id === user.id && setEditing(m)}
                >
                  <td style={{ padding:"11px 14px" }}>
                    <div style={{ fontWeight:500, color:T.text, fontSize:12.5 }}>{m.user_name}</div>
                    <div style={{ fontFamily:T.mono, fontSize:9, color:T.muted }}>{m.user_team_role}</div>
                  </td>
                  <td style={{ padding:"11px 14px" }}><RiskChip level={m.risk_level_confirmed || m.risk_level}/></td>
                  <td style={{ padding:"11px 14px", fontFamily:T.mono, fontSize:11, color:T.muted, maxWidth:180 }}>{(m.risk_detail||"—").slice(0,50)}{m.risk_detail?.length>50?"…":""}</td>
                  <td style={{ padding:"11px 14px" }}><span style={{ fontFamily:T.mono, fontSize:10, background:"#ffffff08", border:`1px solid ${T.border2}`, padding:"2px 7px", borderRadius:2 }}>{m.issue}</span></td>
                  <td style={{ padding:"11px 14px" }}><IssueStatusBadge status={m.issue_status}/></td>
                  <td style={{ padding:"11px 14px" }}><SprintBadge status={m.sprint_status}/></td>
                  <td style={{ padding:"11px 14px", fontFamily:T.mono, fontSize:11, color:T.muted, maxWidth:200 }}>{m.comments.slice(0,60)}{m.comments.length>60?"…":""}</td>
                  <td style={{ padding:"11px 14px", fontFamily:T.mono, fontSize:10, color:T.muted }}>{new Date(m.updated_at).toLocaleString("en-GB",{hour12:false,hour:"2-digit",minute:"2-digit",day:"2-digit",month:"short"})}</td>
                  <td style={{ padding:"11px 14px" }}>{m.user_id===user.id && <Btn variant="ghost" size="xs" onClick={e=>{e.stopPropagation();setEditing(m);}}>Edit</Btn>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing && <UpdateModal member={editing} onSave={handleSave} onClose={() => setEditing(null)} />}
    </>
  );
}
