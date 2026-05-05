/**
 * openclaw/frontend/src/components/Sidebar.jsx + Topbar.jsx + shared chips
 * All exported from this single file for simplicity.
 */
import { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";

// ── Design tokens (inline CSS vars) ──────────────────────────────────────────
export const T = {
  bg:      "#0a0c0f",
  surface: "#0f1318",
  panel:   "#141920",
  border:  "#1e2730",
  border2: "#2a3545",
  text:    "#c8d8e8",
  muted:   "#6e8fa8",
  accent:  "#00d4ff",
  red:     "#ff3b3b",
  orange:  "#ff8c00",
  yellow:  "#f5c400",
  green:   "#00d68f",
  mono:    "'IBM Plex Mono', monospace",
  sans:    "'IBM Plex Sans', sans-serif",
};

export const RISK_META = {
  Critical: { color:T.red,    border:"#ff3b3b55", bg:"#ff3b3b12", dot:"#ff3b3b" },
  Moderate: { color:T.orange, border:"#ff8c0055", bg:"#ff8c0012", dot:"#ff8c00" },
  Minor:    { color:T.yellow, border:"#f5c40055", bg:"#f5c40012", dot:"#f5c400" },
  None:     { color:T.green,  border:"#00d68f55", bg:"#00d68f12", dot:"#00d68f" },
};

export const SPRINT_META = {
  "On Time": { color:T.green,  icon:"▲" },
  "Delayed": { color:T.red,    icon:"▼" },
  "At Risk":  { color:T.orange, icon:"◆" },
};

export const ISSUE_META = {
  "Resolved":    T.green,
  "Open":        T.red,
  "In Progress": T.orange,
};

// ── Chips ─────────────────────────────────────────────────────────────────────

export function RiskChip({ level }) {
  const m = RISK_META[level] || RISK_META.None;
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:6, padding:"3px 9px", borderRadius:2, fontFamily:T.mono, fontSize:10, fontWeight:500, border:`1px solid ${m.border}`, background:m.bg, color:m.color, whiteSpace:"nowrap" }}>
      <span style={{ width:6, height:6, borderRadius:"50%", background:m.dot, flexShrink:0 }} />
      {level}
    </span>
  );
}

export function SprintBadge({ status }) {
  const m = SPRINT_META[status] || {};
  return <span style={{ fontFamily:T.mono, fontSize:10, fontWeight:500, color:m.color }}>{m.icon} {status}</span>;
}

export function IssueStatusBadge({ status }) {
  return <span style={{ fontFamily:T.mono, fontSize:10, fontWeight:500, color:ISSUE_META[status] || T.muted }}>{status}</span>;
}

// ── Button ────────────────────────────────────────────────────────────────────

export function Btn({ children, variant="primary", size="md", onClick, disabled, style={} }) {
  const base = { display:"inline-flex", alignItems:"center", gap:6, borderRadius:3, fontFamily:T.mono, fontWeight:500, cursor:disabled?"not-allowed":"pointer", border:"1px solid", transition:"all 0.12s", letterSpacing:"0.5px", background:"transparent", opacity:disabled?0.4:1 };
  const sizes = { sm:{ padding:"4px 10px", fontSize:10 }, md:{ padding:"7px 14px", fontSize:11 }, xs:{ padding:"3px 8px", fontSize:9 } };
  const variants = {
    primary: { borderColor:T.accent, color:T.accent },
    ghost:   { borderColor:T.border2, color:T.muted },
    danger:  { borderColor:T.red, color:T.red },
  };
  return <button style={{ ...base, ...sizes[size], ...variants[variant], ...style }} onClick={onClick} disabled={disabled}>{children}</button>;
}

// ── Modal ─────────────────────────────────────────────────────────────────────

export function Modal({ title, onClose, footer, children, width }) {
  return (
    <div style={{ position:"fixed", inset:0, background:"#00000088", backdropFilter:"blur(3px)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:200 }}
         onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background:T.panel, border:`1px solid ${T.border2}`, borderRadius:6, width:width||560, maxWidth:"95vw", maxHeight:"90vh", overflowY:"auto" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"16px 20px", borderBottom:`1px solid ${T.border}` }}>
          <span style={{ fontFamily:T.mono, fontSize:12, letterSpacing:2, color:T.accent, textTransform:"uppercase" }}>{title}</span>
          <button style={{ background:"none", border:"none", color:T.muted, cursor:"pointer", fontSize:18 }} onClick={onClose}>×</button>
        </div>
        <div style={{ padding:20 }}>{children}</div>
        {footer && <div style={{ padding:"14px 20px", borderTop:`1px solid ${T.border}`, display:"flex", justifyContent:"flex-end", gap:10 }}>{footer}</div>}
      </div>
    </div>
  );
}

// ── Form field ────────────────────────────────────────────────────────────────

export function Field({ label, children }) {
  return (
    <div style={{ marginBottom:14 }}>
      <label style={{ fontFamily:T.mono, fontSize:10, letterSpacing:"1.5px", color:T.muted, textTransform:"uppercase", display:"block", marginBottom:6 }}>{label}</label>
      {children}
    </div>
  );
}

const inputStyle = { width:"100%", background:T.surface, border:`1px solid ${T.border2}`, borderRadius:3, padding:"8px 12px", color:T.text, fontFamily:T.sans, fontSize:13, outline:"none", boxSizing:"border-box" };
export const Input    = (props) => <input    style={inputStyle} {...props} />;
export const Select   = ({ children, ...props }) => <select style={inputStyle} {...props}>{children}</select>;
export const Textarea = (props) => <textarea style={{ ...inputStyle, minHeight:80, resize:"vertical", fontFamily:T.mono, fontSize:12 }} {...props} />;

// ── Topbar ────────────────────────────────────────────────────────────────────

function useClock() {
  const [t, setT] = useState(new Date());
  useEffect(() => { const i = setInterval(() => setT(new Date()), 1000); return () => clearInterval(i); }, []);
  return t.toLocaleString("en-GB", { hour12:false, hour:"2-digit", minute:"2-digit", second:"2-digit", day:"2-digit", month:"short" });
}

export function Topbar({ user }) {
  const { logout } = useAuth();
  const time = useClock();
  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"0 28px", height:52, borderBottom:`1px solid ${T.border}`, background:T.surface, position:"sticky", top:0, zIndex:100 }}>
      <div style={{ display:"flex", alignItems:"center", gap:16 }}>
        <div style={{ width:7, height:7, borderRadius:"50%", background:T.green, boxShadow:`0 0 8px ${T.green}`, animation:"pulse 2s ease-in-out infinite" }} />
        <span style={{ fontFamily:T.mono, fontSize:13, fontWeight:600, letterSpacing:3, color:T.accent, textTransform:"uppercase" }}>
          Open<span style={{ color:T.muted, fontWeight:300 }}>Claw</span> // TEAM
        </span>
      </div>
      <div style={{ display:"flex", alignItems:"center", gap:20 }}>
        <span style={{ fontFamily:T.mono, fontSize:11, color:T.muted, letterSpacing:1 }}>{time}</span>
        <span style={{ fontFamily:T.mono, fontSize:11, color:T.muted }}>{user?.name} · {user?.role}</span>
        <Btn variant="ghost" size="sm" onClick={logout}>Log out</Btn>
      </div>
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

const NAV = [
  { id:"dashboard", icon:"⬛", label:"Dashboard" },
  { id:"summary",   icon:"◈",  label:"Team Summary" },
  { id:"calendar",  icon:"▦",  label:"Sprint Calendar" },
  { id:"engine",    icon:"⬡",  label:"Engine Control", managerOnly: true },
  { id:"documents", icon:"📁",  label:"Documents" },
  { id:"search",     icon:"⌕",   label:"Search & Summarise" },
  { id:"complexity", icon:"◈",   label:"Complexity" },
  { id:"notes",     icon:"✎",  label:"Notes" },
  { id:"files",     icon:"⬇",  label:"File Manager" },
];

export default function Sidebar({ activePage, onNav, user }) {
  return (
    <aside style={{ width:220, minHeight:"calc(100vh - 52px)", borderRight:`1px solid ${T.border}`, background:T.surface, padding:"20px 0", display:"flex", flexDirection:"column", gap:4, flexShrink:0 }}>
      <div style={{ fontFamily:T.mono, fontSize:9, letterSpacing:2, color:T.muted, textTransform:"uppercase", padding:"14px 20px 6px" }}>Navigation</div>
      {NAV.filter(n => !n.managerOnly || user?.role === "manager").map(n => (
        <div key={n.id}
          onClick={() => onNav(n.id)}
          style={{ display:"flex", alignItems:"center", gap:10, padding:"9px 20px", fontSize:12.5, color:activePage===n.id ? T.accent : "#a0b4c8", cursor:"pointer", borderLeft:activePage===n.id ? `2px solid ${T.accent}` : "2px solid transparent", background:activePage===n.id ? "#00d4ff08" : "transparent", transition:"all 0.12s" }}
          onMouseEnter={e=>{ if(activePage!==n.id) e.currentTarget.style.color="#cde0f0"; }}
          onMouseLeave={e=>{ if(activePage!==n.id) e.currentTarget.style.color="#a0b4c8"; }}
        >
          <span style={{ fontSize:14, width:18, textAlign:"center" }}>{n.icon}</span>
          {n.label}
        </div>
      ))}

      <div style={{ marginTop:"auto", padding:"20px 20px 0", fontFamily:T.mono, fontSize:9, color:T.muted, letterSpacing:1, lineHeight:2 }}>
        SYSTEM<br/>
        <span style={{ color:T.green }}>●</span> Engine Online<br/>
        <span style={{ color:T.green }}>●</span> DB Connected<br/>
        <span style={{ color:"#6e8fa8" }}>●</span> Gmail (stub)<br/>
        <span style={{ color:"#6e8fa8" }}>●</span> Calendar (stub)<br/>
        <span style={{ color:T.green }}>●</span> Web Search (DDG)
      </div>
    </aside>
  );
}
