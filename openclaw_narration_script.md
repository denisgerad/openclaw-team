# OpenClaw — Video Narration Script
# Total runtime: ~4 minutes
# Format: Timestamp | Screen action | Narration
# ─────────────────────────────────────────────────────────────────────────────
# RECORDING SETUP
# ─────────────────────────────────────────────────────────────────────────────
# 1. Open openclaw_primer.html in Chrome or Firefox — full screen (F11)
# 2. Set screen resolution to 1280×720 or 1920×1080
# 3. Use OBS Studio, QuickTime, or Loom to record
# 4. Record your microphone separately if possible (easier to edit)
# 5. Advance slides with → arrow key or Space bar
# 6. Pause 1 second after each slide transition before speaking
# ─────────────────────────────────────────────────────────────────────────────


═══════════════════════════════════════════════════════════════════════════════
SLIDE 1 — TITLE  (0:00 – 0:25)
═══════════════════════════════════════════════════════════════════════════════

  SCREEN: Title slide fades in. "OpenClaw" glows in cyan.
          Ticker scrolls tech stack across the bottom.
          Stats appear: 8 Modules · 4 AI Workers · REST · CLI

  NARRATION:
  ───────────
  "This is OpenClaw — a team automation and intelligence platform
  built for engineering teams that need more than a task tracker.

  OpenClaw brings together sprint risk management, versioned document
  sharing, AI-powered semantic search, and complexity analysis —
  all in one platform, running on your own server.

  Let's walk through what it does."

  TIMING: Speak slowly. Let the ticker and animations settle before starting.
  CUE: Advance slide after "...what it does."


═══════════════════════════════════════════════════════════════════════════════
SLIDE 2 — ARCHITECTURE  (0:25 – 0:55)
═══════════════════════════════════════════════════════════════════════════════

  SCREEN: Architecture diagram animates in — three top nodes, three bottom nodes.
          Tech pill badges appear at the bottom.

  NARRATION:
  ───────────
  "OpenClaw has a clean three-layer architecture.

  The React frontend runs on port 3000 — that's what team members
  open in their browser. It talks to a FastAPI backend on port 8000,
  which handles authentication, document uploads, and all the REST APIs.

  Underneath sits the data layer — SQLite for development,
  PostgreSQL for production, ChromaDB for vector embeddings,
  and the filesystem for actual document files.

  The intelligence layer runs separately — four AI workers powered
  by Mistral, scheduled automatically using APScheduler.
  Each worker is independent, testable, and triggerable on demand.

  The whole stack is Python and React. No Docker required to get started."

  TIMING: Point out each architecture node as you describe it.
  CUE: Advance slide after "...to get started."


═══════════════════════════════════════════════════════════════════════════════
SLIDE 3 — DASHBOARD  (0:55 – 1:25)
═══════════════════════════════════════════════════════════════════════════════

  SCREEN: Mock dashboard UI slides in from the right.
          Stat cards appear: 1 Critical · 1 Delayed · 2 Open · 3 On Track.
          Team status table shows four members with colour-coded risk chips.

  NARRATION:
  ───────────
  "The Dashboard is where the manager and the team see everything
  at a glance — no status meeting required.

  Four stat cards at the top give an instant health summary:
  how many critical risks, delayed sprints, open issues,
  and members on track.

  Below that, the team status table. Every row is a team member.
  You can see their risk level, sprint status, open issue, and
  when they last updated.

  The colour coding is consistent everywhere:
  red for Critical, orange for Moderate, yellow for Minor,
  green for None.

  Risk levels are validated by the AI — if a developer marks
  themselves as Minor but the details say the server is down,
  Mistral will escalate it to Critical automatically."

  TIMING: Pause after each colour description.
  CUE: Advance after "...escalate it to Critical automatically."


═══════════════════════════════════════════════════════════════════════════════
SLIDE 4 — DOCUMENTS  (1:25 – 1:58)
═══════════════════════════════════════════════════════════════════════════════

  SCREEN: Document management UI. Category tabs across the top.
          Table shows four documents with category badges, version numbers,
          owner names, and action buttons.
          Three feature callouts animate in on the left.

  NARRATION:
  ───────────
  "OpenClaw has a full document management system built in.

  Documents are organised into nine categories — Requirements,
  Design, Review, Report, Change Request, Test Plan, Architecture,
  Meeting Notes, and Other.

  Every upload creates a new version. All previous versions are
  retained and downloadable. You can see the full history per document,
  with who uploaded each version and what changed.

  Ownership is tracked — the uploader is the owner.
  Documents can be marked private, visible only to the owner,
  or shared with the whole team by default.

  Downloads are protected — you need a valid login to access any file.
  The manager can delete documents. Developers manage their own."

  TIMING: Pause at each category description.
  CUE: Advance after "...Developers manage their own."


═══════════════════════════════════════════════════════════════════════════════
SLIDE 5 — SEMANTIC SEARCH  (1:58 – 2:32)
═══════════════════════════════════════════════════════════════════════════════

  SCREEN: Search UI. Query bar shows a real question.
          AI synthesis panel appears with a direct answer.
          Two search results shown with relevance scores.
          Four bullet points animate in on the left.

  NARRATION:
  ───────────
  "One of the most powerful features is semantic search
  across all your documents.

  Instead of searching for filenames or keywords, you ask
  a plain English question — like: 'What are the authentication
  requirements for the WebSocket connection?'

  OpenClaw uses Mistral embeddings to find the most relevant
  chunks across every document, every version.

  At the top, you get an AI synthesis — a direct answer to your
  question, citing which documents the information came from.

  Below that, the individual matching chunks, ranked by relevance,
  with the source document, version number, and page reference.

  There are three other modes too — Summarise generates a structured
  summary of any document version. Compare does a semantic diff
  between two versions, telling you what was added, removed,
  changed, and unchanged. The Index Status tab shows which documents
  are embedded and ready to search."

  TIMING: Read the query on screen as you mention it.
  CUE: Advance after "...ready to search."


═══════════════════════════════════════════════════════════════════════════════
SLIDE 6 — COMPLEXITY ANALYSER  (2:32 – 3:05)
═══════════════════════════════════════════════════════════════════════════════

  SCREEN: Complexity table showing four requirements with ratings.
          REQ-007 is expanded showing summary + three factors with
          category tags, factor names, and evidence quotes.
          Legend at the bottom shows four rating bands.

  NARRATION:
  ───────────
  "The Complexity Analyser is designed to solve a problem every
  engineering team faces — requirements and design documents that
  look simple on paper but are actually very hard to build.

  Upload any Requirements or Design document and OpenClaw will
  analyse it section by section using Mistral.

  Each section gets a complexity rating: Simple, Moderate,
  Complex, or Critical — based on the number and type of
  complexity factors found in the text.

  Here you can see REQ-007 — the Real-Time Activity Feed —
  has been rated Complex with a score of six.

  Drilling down, you can see exactly why: WebSocket concurrent
  connection management, JWT authentication on upgrade,
  and per-event RBAC filtering — each one with a direct quote
  from the original requirement as evidence.

  This gives your team concrete data before sprint planning.
  If a requirement scores Critical, that's an architect review.
  If it scores Complex, you need a senior developer and a spike
  before you can estimate it reliably."

  TIMING: Read the factor names clearly. Pause on "evidence."
  CUE: Advance after "...estimate it reliably."


═══════════════════════════════════════════════════════════════════════════════
SLIDE 7 — CLI UPLOAD  (3:05 – 3:30)
═══════════════════════════════════════════════════════════════════════════════

  SCREEN: Terminal window showing a real config + upload session.
          Cursor blinks at the bottom. Five CLI command descriptions
          animate in below the terminal.

  NARRATION:
  ───────────
  "OpenClaw runs on a shared server, and team members connect
  from their own machines. The CLI upload tool makes that seamless.

  It's a single Python script with one dependency — requests.
  Drop it on any developer machine and they're ready in two minutes.

  First-time setup is one command — point it at the server IP
  and log in. Credentials are saved locally, encrypted.

  After that, uploading is one line. Here you can see Aria uploading
  a new requirements PDF from her machine, specifying the category,
  and passing the --analyse flag to automatically trigger
  complexity analysis on the server after the upload completes.

  The CLI also supports bulk uploads, downloading by document ID
  or entire categories, listing documents, and checking
  complexity results — all from the terminal."

  TIMING: Follow the terminal output as you narrate it.
  CUE: Advance after "...all from the terminal."


═══════════════════════════════════════════════════════════════════════════════
SLIDE 8 — ENGINE CONTROL  (3:30 – 3:52)
═══════════════════════════════════════════════════════════════════════════════

  SCREEN: Engine control panel. Four worker cards — all green.
          Summary stats: 4/4 healthy, 284 total runs.
          Activity log at the bottom shows last three events.

  NARRATION:
  ───────────
  "Behind all of this runs the OpenClaw Engine — four modular
  AI workers that operate automatically in the background.

  The Risk Classifier runs every five minutes, validating
  team member risk levels against what Mistral actually
  thinks the severity is.

  The Digest Generator fires every morning at eight, building
  a plain-English team summary and sending it by email.

  The Reminder Engine checks every hour for stale status updates
  or approaching sprint deadlines, and sends targeted reminders
  to the relevant developer.

  The Workflow Triggers worker runs every two minutes, processing
  database events — automatically escalating critical risks,
  sending onboarding emails, and firing any custom rules you add.

  All four workers run on startup, recover from failures
  automatically, and can be triggered manually from the UI
  before a standup or planning session."

  TIMING: Name each worker clearly. Pause after each one.
  CUE: Advance after "...planning session."


═══════════════════════════════════════════════════════════════════════════════
SLIDE 9 — CLOSING  (3:52 – 4:10)
═══════════════════════════════════════════════════════════════════════════════

  SCREEN: Closing slide. Heading: "Built for teams that ship fast."
          Eight module badges float gently.
          OpenClaw logo and version at the bottom.

  NARRATION:
  ───────────
  "OpenClaw is a single platform that brings together everything
  your engineering team needs to stay aligned — sprint visibility,
  document management, AI search, complexity analysis,
  and automated intelligence — all self-hosted, all yours.

  It's built on FastAPI, React, Mistral AI, and ChromaDB,
  and it runs anywhere Python runs.

  Thank you for watching."

  TIMING: Speak slowly. Let the floating modules settle.
  CUE: End recording here.


═══════════════════════════════════════════════════════════════════════════════
POST-PRODUCTION NOTES
═══════════════════════════════════════════════════════════════════════════════

TITLES TO ADD IN EDITOR (optional):
  0:00  — Lower third: "OpenClaw — Platform Overview"
  0:25  — Lower third: "Architecture"
  0:55  — Lower third: "Team Dashboard"
  1:25  — Lower third: "Document Management"
  1:58  — Lower third: "Semantic Search & AI Summarisation"
  2:32  — Lower third: "Complexity Analyser"
  3:05  — Lower third: "CLI Upload Tool"
  3:30  — Lower third: "Engine Control"
  3:52  — Lower third: "OpenClaw // v1.0"

MUSIC (optional):
  Low-key electronic / ambient. Suggested search terms:
  "Lofi tech background music no copyright"
  "Dark ambient corporate background"
  Keep under -18 dB so narration is always clearly audible.

SCREEN RECORDING TIPS:
  - Use 1280×720 capture to match the slide dimensions exactly
  - Advance slides with → or Space — both are smooth and silent
  - Wait 0.5–1 second after each transition before speaking
  - If you stumble on a word, pause 2 seconds and re-say the sentence
    — easy to cut in post
  - Record the full presentation twice — use the better take

TOOLS:
  Free recording: OBS Studio (Windows/Mac/Linux)
  Simple recording: Loom (browser extension, free tier)
  Mac: QuickTime → File → New Screen Recording
  Editing: DaVinci Resolve (free), iMovie (Mac), CapCut (online)
