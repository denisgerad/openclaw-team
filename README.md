# OpenClaw

An AI-assisted team management and document intelligence platform for engineering teams.
Built with **FastAPI** + **React/Vite**, powered by **Mistral AI**.

---

## Project Overview

OpenClaw helps engineering teams manage sprint health, track member status, and analyse
the complexity of requirements and design documents. An autonomous background engine
continuously monitors the team and fires alerts, digests, and workflow triggers — without
manual intervention.

Key capabilities:

| Feature | Description |
|---|---|
| **Dashboard** | Live team status, risk flags, and activity feed per member |
| **Team Summary** | AI-generated team-wide narrative using Mistral |
| **Sprint Calendar** | Sprint board with task tracking and velocity stats |
| **Documents** | Version-controlled document store (PDF, DOCX, XLSX, PPTX, TXT) |
| **Search & Summarise** | Semantic search over all documents; compare/summarise with Mistral |
| **Complexity Analyser** | Mistral-powered section-level complexity scoring for Requirements & Design docs |
| **Engine Control** | Manager view of the autonomous background engine and worker logs |
| **Notes** | Personal markdown notes per user |
| **File Manager** | General file upload/download store |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser  (React + Vite, port 3000)                         │
│  pages: Dashboard · Summary · Calendar · Documents ·        │
│         Search · Complexity · Engine · Notes · Files        │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/JSON  (proxied by Vite dev server)
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI  (Uvicorn, port 8000)                              │
│                                                             │
│  api/          ← REST routers (one file per feature)        │
│  engine/       ← APScheduler workers (async background)     │
│  search/       ← ChromaDB pipeline + Mistral calls          │
│  db/           ← SQLAlchemy 2 async ORM + SQLite            │
│  integrations/ ← DuckDuckGo web search                      │
└──────┬──────────────────┬──────────────────────────────────-┘
       │                  │
  SQLite DB          ChromaDB (local)      Mistral AI (API)
  openclaw.db        chroma_db/            api.mistral.ai
```

**Request flow:**
1. React SPA authenticates with JWT (`POST /api/auth/login`)
2. All subsequent calls carry `Authorization: Bearer <token>`
3. FastAPI validates the token and dispatches to the appropriate router
4. Background engine (APScheduler) runs workers every few minutes independently of HTTP traffic

---

## Module Descriptions

### Backend (`backend/`)

| Path | Purpose |
|---|---|
| `main.py` | App factory — mounts all routers, starts DB, launches engine |
| `config.py` | Pydantic settings — reads `backend/.env` |
| `api/auth.py` | JWT login/logout, user registration, Google OAuth stub |
| `api/status.py` | Member status updates (mood, risk, blockers, sprint status) |
| `api/sprint.py` | Sprint CRUD, task management, velocity calculation |
| `api/documents.py` | Versioned document upload/download/delete; triggers ChromaDB indexing |
| `api/search.py` | Semantic search, AI summarise, AI compare, AI synthesise |
| `api/complexity.py` | Complexity analysis trigger, result/section/factor retrieval, stats |
| `api/engine.py` | Engine worker status, manual trigger, log tail |
| `api/notes_files.py` | Personal notes and general file store |
| `db/models.py` | Core ORM: `User`, `StatusUpdate`, `Sprint`, `SprintTask`, etc. |
| `db/document_models.py` | `Document`, `DocumentVersion` ORM models |
| `db/session.py` | Async engine, session factory, `init_db()` (auto-creates all tables) |
| `db/seed.py` | Seed script — creates Manager + Developer demo accounts |
| `engine/scheduler.py` | APScheduler setup; registers all workers |
| `engine/workers/risk_classifier.py` | Classifies each member's risk level using Mistral + web search |
| `engine/workers/reminder_engine.py` | Detects stale updates and sprint deadline proximity; sends reminders |
| `engine/workers/digest_generator.py` | Generates and emails a daily team digest |
| `engine/workers/workflow_triggers.py` | Fires automated workflow events (escalation, sprint warnings) |
| `search/extractor.py` | Extracts plain text from PDF, DOCX, XLSX, PPTX, TXT |
| `search/chunker.py` | Splits text into overlapping chunks for embedding |
| `search/chroma_store.py` | ChromaDB read/write wrapper |
| `search/pipeline.py` | End-to-end indexing pipeline: extract → chunk → embed → store |
| `search/startup_indexer.py` | Re-indexes any unindexed documents on server startup |
| `search/summariser.py` | Mistral summarise/compare/synthesise calls |
| `search/complexity_analyser.py` | Section splitter + per-section Mistral scoring pipeline |
| `search/complexity_models.py` | ORM: `ComplexityResult`, `ComplexitySection`, `ComplexityFactor` |

### Frontend (`frontend/src/`)

| Path | Purpose |
|---|---|
| `App.jsx` | Root shell — auth gate, page routing |
| `AuthContext.jsx` | JWT auth context and `useAuth()` hook |
| `components/Sidebar.jsx` | Left nav, topbar, shared UI tokens (`T`), `Btn`, `RatingChip` |
| `pages/Dashboard.jsx` | Live status cards, risk flags, activity feed |
| `pages/TeamSummary.jsx` | AI-generated team narrative |
| `pages/CalendarPage.jsx` | Sprint board and task tracker |
| `pages/DocumentsPage.jsx` | Document library with version history |
| `pages/SearchPage.jsx` | Semantic search UI with AI answer panel |
| `pages/ComplexityPage.jsx` | Complexity analyser — section drill-down, factor table, stats |
| `pages/EngineControl.jsx` | Worker status, manual triggers, log viewer |
| `pages/NotesPage.jsx` | Personal markdown notes |
| `pages/FilesPage.jsx` | General file manager |

---

## Installation & Setup

### Prerequisites

- Python 3.12
- Node.js 18+
- A [Mistral AI](https://console.mistral.ai/) API key

### 1 — Clone and configure

```bash
git clone https://github.com/denisgerad/openclaw-team.git
cd openclaw-team
```

Copy the example env file and fill in your values:

```bash
cp backend/.env.example backend/.env
# edit backend/.env — see Environment Variables section below
```

### 2 — Backend

```bash
cd /path/to/openclaw-team
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate

pip install -r backend/requirements.txt

# Seed the database with demo accounts (run once)
python -m backend.db.seed
```

### 3 — Frontend

```bash
cd frontend
npm install
```

---

## Running (Development)

Open two terminals:

**Terminal 1 — Backend**
```bash
cd /path/to/openclaw-team
source backend/.venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

Open `http://localhost:3000` in your browser.

> **Tables are created automatically** on first backend startup — no migration commands needed.

---

## Running as a Network Server (access from other machines)

### 1 — Bind backend to all interfaces

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 2 — Expose the frontend dev server

In `frontend/vite.config.js`, ensure the server section allows external hosts:

```js
server: {
  host: "0.0.0.0",
  port: 3000,
  proxy: { "/api": "http://localhost:8000" }
}
```

Then run:
```bash
npm run dev -- --host 0.0.0.0
```

### 3 — Find the server's IP

```bash
ip addr show eth0   # Linux / WSL
```

Other machines connect to `http://<server-ip>:3000`.

### WSL on Windows — port forwarding (run in PowerShell as Administrator)

Replace `<WSL_IP>` with the IP from the command above:

```powershell
netsh interface portproxy add v4tov4 listenport=3000 listenaddress=0.0.0.0 connectport=3000 connectaddress=<WSL_IP>
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=<WSL_IP>
```

To remove:
```powershell
netsh interface portproxy delete v4tov4 listenport=3000 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
```

---

## Demo Accounts

| Role | Email | Password |
|---|---|---|
| Manager | `manager@openclaw.dev` | `manager123` |
| Developer | `aria@openclaw.dev` | `dev123` |

Managers have access to Engine Control and can see all team members.

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and set the following:

```env
# ── Mistral AI (required) ─────────────────────────────────────────────────────
# Get your key at https://console.mistral.ai/
MISTRAL_API_KEY=your-mistral-api-key-here
MISTRAL_MODEL=mistral-small-latest

# ── Database ──────────────────────────────────────────────────────────────────
# SQLite (default, no setup needed — file created automatically)
DATABASE_URL=sqlite+aiosqlite:///./openclaw.db

# PostgreSQL (production — uncomment and fill in)
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/openclaw

# ── Security ──────────────────────────────────────────────────────────────────
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=change-this-to-a-random-64-char-hex-string

JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# Fernet key for token encryption — generate with:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
TOKEN_ENCRYPTION_KEY=your-fernet-key-here

# ── Application ───────────────────────────────────────────────────────────────
APP_NAME=OpenClaw
APP_ENV=development          # set to "production" in prod

# Comma-separated list of emails to receive the daily digest
DIGEST_RECIPIENTS=manager@yourcompany.com

# ── Web Search (optional) ─────────────────────────────────────────────────────
# Uses DuckDuckGo — no API key required
WEB_SEARCH_ENABLED=true

# ── Google OAuth (optional) ───────────────────────────────────────────────────
# GOOGLE_CLIENT_ID=
# GOOGLE_CLIENT_SECRET=
# GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/oauth/callback
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI 0.111 + Uvicorn |
| ORM | SQLAlchemy 2.0 async |
| Database (dev) | SQLite + aiosqlite |
| Database (prod) | PostgreSQL + asyncpg |
| Vector store | ChromaDB 0.5.3 (local persistent) |
| AI | Mistral AI (`mistral-small-latest` for analysis, `mistral-embed` for embeddings) |
| Background jobs | APScheduler 3.10 |
| Auth | JWT (python-jose) + bcrypt |
| Frontend | React 18 + Vite |
| Document parsing | PyMuPDF, python-docx, openpyxl, python-pptx |
