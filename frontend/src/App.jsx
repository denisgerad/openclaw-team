import { useState } from "react";
import { AuthProvider, useAuth } from "./AuthContext";
import LoginPage     from "./pages/LoginPage";
import Dashboard     from "./pages/Dashboard";
import TeamSummary   from "./pages/TeamSummary";
import EngineControl from "./pages/EngineControl";
import NotesPage     from "./pages/NotesPage";
import FilesPage      from "./pages/FilesPage";
import CalendarPage   from "./pages/CalendarPage";
import DocumentsPage  from "./pages/DocumentsPage";
import SearchPage      from "./pages/SearchPage";
import ComplexityPage  from "./pages/ComplexityPage";
import Sidebar, { Topbar } from "./components/Sidebar";

const PAGES = {
  dashboard: Dashboard,
  summary:   TeamSummary,
  calendar:  CalendarPage,
  documents: DocumentsPage,
  search:      SearchPage,
  complexity:  ComplexityPage,
  engine:    EngineControl,
  notes:     NotesPage,
  files:     FilesPage,
};

function Shell() {
  const { user, loading } = useAuth();
  const [page, setPage]   = useState("dashboard");

  if (loading) return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:"100vh", background:"#0a0c0f", color:"#00d4ff", fontFamily:"IBM Plex Mono, monospace", fontSize:13 }}>
      OPENCLAW // INITIALISING…
    </div>
  );

  if (!user) return <LoginPage />;

  const PageComponent = PAGES[page] || Dashboard;

  return (
    <div style={{ display:"flex", flexDirection:"column", minHeight:"100vh", background:"#0a0c0f" }}>
      <Topbar user={user} />
      <div style={{ display:"flex", flex:1 }}>
        <Sidebar activePage={page} onNav={setPage} user={user} />
        <main style={{ flex:1, padding:"24px 28px", overflow:"auto" }}>
          <PageComponent user={user} />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
