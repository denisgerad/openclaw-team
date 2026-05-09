/**
 * openclaw/frontend/src/components/NotificationBell.jsx
 *
 * Bell icon component mounted in the Topbar.
 *
 * Features:
 *  - Red badge with unread count
 *  - Polls GET /api/notifications/count every 30 seconds
 *  - Click opens dropdown panel — most recent 30 notifications
 *  - Unread items highlighted with left accent border
 *  - Click individual notification → navigates to link_page, marks as read
 *  - "Mark all read" button
 *  - Closes on outside click or Escape
 *  - Animated entry / exit
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { T } from "./Sidebar";

// ── API helpers ───────────────────────────────────────────────────────────────
const hdr = () => ({ "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("oc_token")}` });

async function fetchCount() {
  try {
    const res = await fetch("/api/notifications/count", { headers: hdr() });
    if (!res.ok) return 0;
    return (await res.json()).unread || 0;
  } catch { return 0; }
}

async function fetchNotifications() {
  try {
    const res = await fetch("/api/notifications?limit=30", { headers: hdr() });
    if (!res.ok) return [];
    return await res.json();
  } catch { return []; }
}

async function markRead(notifId = null) {
  try {
    await fetch("/api/notifications/read", {
      method: "POST",
      headers: hdr(),
      body: JSON.stringify({ notif_id: notifId }),
    });
  } catch {}
}

// ── Notification type metadata ─────────────────────────────────────────────
const TYPE_META = {
  document_uploaded:   { icon: "📄", color: "#7dd3fc" },
  risk_critical:       { icon: "🔴", color: "#ff3b3b" },
  risk_escalated:      { icon: "🟠", color: "#ff8c00" },
  sprint_delayed:      { icon: "⚠️", color: "#ff8c00" },
  complexity_complete: { icon: "◎",  color: "#00d68f" },
  member_joined:       { icon: "👤", color: "#c4b5fd" },
  digest_sent:         { icon: "📧", color: "#6e8fa8" },
  mention:             { icon: "💬", color: "#00d4ff" },
};

function fmtRelTime(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)     return "just now";
  if (diff < 3600)   return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ── Main component ─────────────────────────────────────────────────────────
export default function NotificationBell({ onNavigate }) {
  const [count,    setCount]    = useState(0);
  const [open,     setOpen]     = useState(false);
  const [notifs,   setNotifs]   = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [prevCount, setPrevCount] = useState(0);
  const [shake,    setShake]    = useState(false);
  const panelRef  = useRef(null);
  const bellRef   = useRef(null);

  // ── Poll for unread count every 30s ────────────────────────────────────────
  const pollCount = useCallback(async () => {
    const n = await fetchCount();
    setCount(c => {
      if (n > c && c !== 0) {
        // New notification arrived — shake the bell
        setShake(true);
        setTimeout(() => setShake(false), 600);
      }
      return n;
    });
  }, []);

  useEffect(() => {
    pollCount();
    const interval = setInterval(pollCount, 10000);
    return () => clearInterval(interval);
  }, [pollCount]);

  // ── Open panel — load notifications ───────────────────────────────────────
  async function handleOpen() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    setLoading(true);
    const data = await fetchNotifications();
    setNotifs(data);
    setLoading(false);
  }

  // ── Close on outside click or Escape ──────────────────────────────────────
  useEffect(() => {
    if (!open) return;
    function handleClick(e) {
      if (panelRef.current && !panelRef.current.contains(e.target) &&
          bellRef.current   && !bellRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    function handleKey(e) { if (e.key === "Escape") setOpen(false); }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown",   handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown",   handleKey);
    };
  }, [open]);

  // ── Click a notification ──────────────────────────────────────────────────
  async function handleNotifClick(n) {
    if (!n.is_read) {
      await markRead(n.id);
      setNotifs(ns => ns.map(x => x.id === n.id ? { ...x, is_read: true } : x));
      setCount(c => Math.max(0, c - 1));
    }
    if (n.link_page && onNavigate) {
      onNavigate(n.link_page);
      setOpen(false);
    }
  }

  // ── Mark all read ─────────────────────────────────────────────────────────
  async function handleMarkAll() {
    await markRead(null);
    setNotifs(ns => ns.map(n => ({ ...n, is_read: true })));
    setCount(0);
  }

  const unreadCount = notifs.filter(n => !n.is_read).length;

  return (
    <>
      <style>{`
        @keyframes bellShake {
          0%,100%{transform:rotate(0)}
          15%{transform:rotate(15deg)}
          30%{transform:rotate(-12deg)}
          45%{transform:rotate(10deg)}
          60%{transform:rotate(-8deg)}
          75%{transform:rotate(5deg)}
          90%{transform:rotate(-3deg)}
        }
        @keyframes notifSlide {
          from{opacity:0;transform:translateY(-8px)}
          to{opacity:1;transform:translateY(0)}
        }
        .bell-shake { animation: bellShake 0.6s ease; }
        .notif-panel { animation: notifSlide 0.2s ease; }
        .notif-item { transition: background 0.12s; }
        .notif-item:hover { background: #ffffff06 !important; }
      `}</style>

      {/* ── Bell button ── */}
      <div
        ref={bellRef}
        onClick={handleOpen}
        style={{
          position: "relative", cursor: "pointer",
          width: 36, height: 36,
          display: "flex", alignItems: "center", justifyContent: "center",
          borderRadius: 3,
          border: `1px solid ${open ? T.accent + "66" : T.border}`,
          background: open ? "#00d4ff0a" : "transparent",
          transition: "all 0.15s",
        }}
        title="Notifications"
      >
        {/* Bell icon */}
        <span
          className={shake ? "bell-shake" : ""}
          style={{ fontSize: 16, lineHeight: 1, userSelect: "none" }}
        >
          🔔
        </span>

        {/* Unread badge */}
        {count > 0 && (
          <div style={{
            position: "absolute", top: -6, right: -6,
            minWidth: 16, height: 16,
            background: T.red,
            borderRadius: 8,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: T.mono, fontSize: 9, fontWeight: 700,
            color: "#fff",
            padding: "0 4px",
            boxShadow: `0 0 8px ${T.red}88`,
            animation: "none",
          }}>
            {count > 99 ? "99+" : count}
          </div>
        )}
      </div>

      {/* ── Dropdown panel ── */}
      {open && (
        <div
          ref={panelRef}
          className="notif-panel"
          style={{
            position: "fixed",
            top: 56,
            right: "calc(50% - 640px + 12px)",  // align near topbar right
            width: 380,
            maxHeight: 520,
            background: T.panel,
            border: `1px solid ${T.border2}`,
            borderRadius: 6,
            boxShadow: "0 20px 60px #00000088, 0 0 30px #00d4ff11",
            zIndex: 500,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Panel header */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "12px 16px",
            borderBottom: `1px solid ${T.border}`,
            background: "var(--surface, #0f1318)",
            flexShrink: 0,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontFamily: T.mono, fontSize: 11, letterSpacing: 2, color: T.accent, textTransform: "uppercase" }}>
                Notifications
              </span>
              {unreadCount > 0 && (
                <span style={{ fontFamily: T.mono, fontSize: 9, color: T.red, border: `1px solid ${T.red}44`, background: `${T.red}12`, padding: "1px 6px", borderRadius: 2 }}>
                  {unreadCount} unread
                </span>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAll}
                  style={{ fontFamily: T.mono, fontSize: 9, color: T.muted, background: "none", border: `1px solid ${T.border}`, borderRadius: 2, padding: "3px 8px", cursor: "pointer", letterSpacing: 1 }}
                >
                  Mark all read
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                style={{ fontFamily: T.mono, fontSize: 14, color: T.muted, background: "none", border: "none", cursor: "pointer", lineHeight: 1 }}
              >
                ×
              </button>
            </div>
          </div>

          {/* Notification list */}
          <div style={{ overflowY: "auto", flex: 1 }}>
            {loading && (
              <div style={{ padding: 40, textAlign: "center", fontFamily: T.mono, fontSize: 11, color: T.muted }}>
                Loading…
              </div>
            )}

            {!loading && notifs.length === 0 && (
              <div style={{ padding: 40, textAlign: "center" }}>
                <div style={{ fontSize: 28, marginBottom: 10 }}>🔔</div>
                <div style={{ fontFamily: T.mono, fontSize: 11, color: T.muted }}>No notifications yet</div>
                <div style={{ fontFamily: T.mono, fontSize: 9, color: T.muted, marginTop: 6, letterSpacing: 1 }}>
                  You'll be notified when team members upload documents, change risk levels, or delay sprints
                </div>
              </div>
            )}

            {!loading && notifs.map((n, i) => {
              const meta = TYPE_META[n.notif_type] || { icon: "●", color: T.muted };
              return (
                <div
                  key={n.id}
                  className="notif-item"
                  onClick={() => handleNotifClick(n)}
                  style={{
                    display: "flex", gap: 12, padding: "11px 16px",
                    borderBottom: i < notifs.length - 1 ? `1px solid ${T.border}` : "none",
                    cursor: n.link_page ? "pointer" : "default",
                    borderLeft: n.is_read ? "3px solid transparent" : `3px solid ${meta.color}`,
                    background: n.is_read ? "transparent" : `${meta.color}08`,
                  }}
                >
                  {/* Icon */}
                  <div style={{ fontSize: 18, flexShrink: 0, lineHeight: 1, marginTop: 2 }}>
                    {meta.icon}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 12.5,
                      fontWeight: n.is_read ? 400 : 500,
                      color: n.is_read ? T.muted : T.text,
                      lineHeight: 1.4,
                      marginBottom: 3,
                    }}>
                      {n.title}
                    </div>
                    {n.body && (
                      <div style={{
                        fontFamily: T.mono, fontSize: 10,
                        color: T.muted, lineHeight: 1.5,
                        overflow: "hidden",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                      }}>
                        {n.body}
                      </div>
                    )}
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 5 }}>
                      <span style={{ fontFamily: T.mono, fontSize: 9, color: T.muted }}>
                        {fmtRelTime(n.created_at)}
                      </span>
                      {n.link_page && (
                        <span style={{ fontFamily: T.mono, fontSize: 9, color: meta.color, opacity: 0.7 }}>
                          → {n.link_page}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Unread dot */}
                  {!n.is_read && (
                    <div style={{
                      width: 6, height: 6, borderRadius: "50%",
                      background: meta.color,
                      flexShrink: 0, marginTop: 6,
                      boxShadow: `0 0 6px ${meta.color}`,
                    }}/>
                  )}
                </div>
              );
            })}
          </div>

          {/* Footer */}
          {notifs.length > 0 && (
            <div style={{
              padding: "8px 16px",
              borderTop: `1px solid ${T.border}`,
              background: "var(--surface, #0f1318)",
              fontFamily: T.mono, fontSize: 9,
              color: T.muted, textAlign: "center",
              flexShrink: 0,
            }}>
              {notifs.length} notification{notifs.length !== 1 ? "s" : ""} · auto-refreshes every 10s
            </div>
          )}
        </div>
      )}
    </>
  );
}
