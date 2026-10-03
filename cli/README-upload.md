# OpenClaw — Developer Upload Guide

How to upload documents from your local machine to the shared OpenClaw server.

---

## What you need

- Python 3.9 or later (check: `python3 --version`)
- The `requests` library (`pip install requests`)
- The OpenClaw server IP address from your manager
- Your OpenClaw account email and password

---

## Setup (one time only)

### 1. Get the CLI files

Copy these two files from the `cli/` folder in the repository to anywhere on your machine:

```
openclaw-upload.py      ← the CLI tool (required)
openclaw-upload.sh      ← Linux/Mac wrapper (optional, for convenience)
openclaw-upload.bat     ← Windows wrapper (optional, for convenience)
```

### 2. Install the only dependency

```bash
pip install requests
```

### 3. Configure your connection

```bash
python openclaw-upload.py config \
    --server http://192.168.1.50:8000 \
    --email  your.name@team.com
```

You will be prompted for your password. Credentials are saved to `~/.openclaw.json` (readable only by you).

**Verify it works:**
```bash
python openclaw-upload.py ping
```

Expected output:
```
Pinging http://192.168.1.50:8000 …
✓ Server reachable
  App     : OpenClaw
  Version : 1.0.0
  Max upload : 200 MB
```

---

## Uploading documents

### Upload a single file

```bash
python openclaw-upload.py upload \
    --file ./my-requirements.pdf \
    --category Requirements \
    --name "Authentication Requirements v1" \
    --note "Initial draft for review"
```

### Upload multiple files at once

```bash
python openclaw-upload.py upload \
    --file ./req_v2.pdf ./design_v1.docx ./api_spec.pdf \
    --category Design \
    --note "Sprint 14 design documents"
```

### Upload as a new version of an existing document

First find the document ID:
```bash
python openclaw-upload.py list
```

Then upload with `--doc-id`:
```bash
python openclaw-upload.py upload \
    --file ./requirements_v3.pdf \
    --doc-id 12 \
    --note "Revised after review meeting — section 4 updated"
```

### Upload and trigger complexity analysis automatically

```bash
python openclaw-upload.py upload \
    --file ./system_requirements.pdf \
    --category Requirements \
    --analyse
```

This uploads the file and immediately queues a complexity analysis. Check the result:
```bash
python openclaw-upload.py status --version-id <VERSION_ID>
```

### Upload a private document (only visible to you)

```bash
python openclaw-upload.py upload \
    --file ./draft-notes.docx \
    --category "Meeting Notes" \
    --private
```

---

## Available document categories

| Category | Use for |
|---|---|
| Requirements | Functional and non-functional requirements |
| Design | Architecture, component design, API specs |
| Review | Code reviews, design reviews, audit findings |
| Report | Sprint reports, test reports, status reports |
| Change Request | RFC documents, change proposals |
| Test Plan | Test strategies, test cases, QA plans |
| Architecture | System architecture, ADRs, infrastructure diagrams |
| Meeting Notes | Standup notes, retrospectives, decision logs |
| Other | Anything else |

---

## All commands

| Command | What it does |
|---|---|
| `config` | Save server URL and login credentials |
| `ping` | Test server connection |
| `upload` | Upload one or more files |
| `list` | List documents on the server |
| `status` | Show complexity analysis result for a version |
| `analyse` | Trigger complexity analysis for a version |

### Full flag reference

```
upload flags:
  --file PATH [PATH ...]   File(s) to upload (required)
  --category CATEGORY      Document category (prompted if omitted)
  --name NAME              Document name (single file only)
  --name-prefix PREFIX     Prefix for auto-names in multi-file uploads
  --description TEXT       Short description
  --note TEXT              Change note (what's new in this version)
  --doc-id ID              Upload as new version of existing document
  --private                Make document private (only you can see it)
  --analyse                Trigger complexity analysis after upload

list flags:
  --category CATEGORY      Filter by category

ping flags:
  --server URL             Test a different server (overrides saved config)

config flags:
  --server URL             Server URL
  --email EMAIL            Your email
  --password PASSWORD      Password (prompted if omitted)
  --show                   Show current saved configuration
```

---

## Network requirements

The OpenClaw server must be reachable from your machine on **port 8000** (API).

| Scenario | What to do |
|---|---|
| Same office LAN | Use the server's LAN IP: `http://192.168.1.50:8000` |
| VPN connected | Use the server's VPN IP |
| Remote / home | Ask your manager to set up a VPN or expose OpenClaw via HTTPS |
| Cannot connect | Run `ping 192.168.1.50` to verify basic network access |

---

## Troubleshooting

**"Cannot reach server"**
- Check the server IP is correct
- Check you are on the same network or VPN
- Ask your manager to confirm the server is running: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

**"Login failed"**
- Check your email and password
- Ask your manager to verify your account exists in OpenClaw

**"File too large"**
- The server default is 200 MB. Ask your manager to increase `MAX_UPLOAD_MB` in the server `.env`

**"Session expired"**
- Re-run: `python openclaw-upload.py config --server <URL> --email <EMAIL>`

**Config location**
- Your saved credentials are at: `~/.openclaw.json` (Linux/Mac) or `C:\Users\YourName\.openclaw.json` (Windows)
- To reset: delete this file and run `config` again

---

## Server-side setup (for the manager)

To accept connections from developer machines:

**1. Add developer machine IPs to CORS in `.env`:**
```
ALLOWED_ORIGINS=http://localhost:3000,http://192.168.1.50:3000,http://192.168.1.51:3000
SERVER_URL=http://192.168.1.50:8000
MAX_UPLOAD_MB=200
```

**2. Start the server bound to all interfaces (not just localhost):**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The `--host 0.0.0.0` flag is what makes the server reachable from other machines.
Without it, the server only listens on `127.0.0.1` (the server machine itself).

**3. Verify from a developer machine:**
```bash
curl http://192.168.1.50:8000/api/server-info
```

Should return JSON with app name, version, and upload limits.
