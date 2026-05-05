#!/usr/bin/env python3
"""
openclaw-upload.py
==================
CLI tool for uploading documents from a developer's local machine
to a remote OpenClaw server.

REQUIREMENTS (standard library only + requests):
    pip install requests

QUICK START:
    # First-time setup — saves credentials to ~/.openclaw.json
    python openclaw-upload.py config \
        --server http://192.168.1.50:8000 \
        --email  aria@yourteam.com

    # Upload a single file
    python openclaw-upload.py upload \
        --file ./requirements_v2.pdf \
        --category Requirements \
        --name "System Requirements v2" \
        --note "Added auth flow section 4"

    # Upload multiple files at once
    python openclaw-upload.py upload \
        --file ./req_v2.pdf ./design_v1.pdf ./review.docx \
        --category Requirements

    # Upload as a new version of an existing document
    python openclaw-upload.py upload \
        --file ./requirements_v3.pdf \
        --doc-id 12 \
        --note "Revised after review meeting"

    # List documents on the server
    python openclaw-upload.py list
    python openclaw-upload.py list --category Design

    # Check server connection
    python openclaw-upload.py ping

    # Show saved config
    python openclaw-upload.py config --show
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed.")
    print("Run:  pip install requests")
    sys.exit(1)

# ── Config file ───────────────────────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".openclaw.json"

VALID_CATEGORIES = [
    "Requirements", "Design", "Review", "Report",
    "Change Request", "Test Plan", "Architecture",
    "Meeting Notes", "Other",
]

RATING_ICONS = {
    "Simple": "🟢", "Moderate": "🟡",
    "Complex": "🟠", "Critical": "🔴",
}

# ── ANSI colours ─────────────────────────────────────────────────────────────
def _c(text, code): return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text
def green(t):  return _c(t, "32")
def yellow(t): return _c(t, "33")
def red(t):    return _c(t, "31")
def cyan(t):   return _c(t, "36")
def bold(t):   return _c(t, "1")
def dim(t):    return _c(t, "2")


# ── Config helpers ────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    CONFIG_PATH.chmod(0o600)   # owner read/write only


def require_config() -> dict:
    cfg = load_config()
    if not cfg.get("server") or not cfg.get("token"):
        print(red("Not configured. Run:"))
        print(f"  python openclaw-upload.py config --server <SERVER_URL> --email <EMAIL>")
        sys.exit(1)
    return cfg


# ── API client ────────────────────────────────────────────────────────────────

class OpenClawClient:
    def __init__(self, server: str, token: str | None = None):
        self.server  = server.rstrip("/")
        self.token   = token
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _url(self, path: str) -> str:
        return f"{self.server}/api{path}"

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.session.get(self._url(path), **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.session.post(self._url(path), **kwargs)

    def ping(self) -> dict:
        """Check server connection — no auth required."""
        try:
            r = self.session.get(self._url("/server-info"), timeout=8)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError:
            raise SystemExit(red(f"Cannot reach server at {self.server}\nCheck SERVER_URL and network connection."))
        except requests.exceptions.Timeout:
            raise SystemExit(red(f"Server timed out: {self.server}"))

    def login(self, email: str, password: str) -> str:
        """Authenticate and return JWT token."""
        r = self.session.post(
            self._url("/auth/login"),
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        if r.status_code == 401:
            raise SystemExit(red("Login failed — check email and password."))
        r.raise_for_status()
        return r.json()["access_token"]

    def upload_file(
        self,
        file_path:   Path,
        name:        str,
        category:    str,
        description: str = "",
        change_note: str = "Uploaded via CLI",
        is_private:  bool = False,
        doc_id:      int | None = None,
    ) -> dict:
        """Upload a file. Returns the document response dict."""
        with open(file_path, "rb") as f:
            files   = {"file": (file_path.name, f, _guess_mime(file_path))}
            data    = {
                "name":        name,
                "category":    category,
                "description": description,
                "change_note": change_note,
                "is_private":  str(is_private).lower(),
            }
            if doc_id is not None:
                data["doc_id"] = str(doc_id)

            r = self.session.post(
                self._url("/docs/upload"),
                files=files,
                data=data,
                timeout=300,   # large files can take time
            )

        if r.status_code == 413:
            err = r.json().get("detail", "File too large")
            raise SystemExit(red(f"Upload rejected: {err}"))
        if r.status_code == 401:
            raise SystemExit(red("Session expired. Re-run: python openclaw-upload.py config --server <URL> --email <EMAIL>"))
        r.raise_for_status()
        return r.json()

    def list_docs(self, category: str | None = None) -> list[dict]:
        params = {}
        if category:
            params["category"] = category
        r = self.get("/docs", params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def get_complexity(self, version_id: int) -> dict | None:
        try:
            r = self.get(f"/complexity/result/{version_id}", timeout=15)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def trigger_complexity(self, version_id: int) -> None:
        try:
            r = self.post(f"/complexity/analyse/{version_id}", timeout=10)
            r.raise_for_status()
        except Exception:
            pass  # non-fatal

    def get_doc(self, doc_id: int) -> dict:
        """Fetch a document with its version list."""
        r = self.get(f"/docs/{doc_id}", timeout=15)
        if r.status_code == 404:
            raise SystemExit(red(f"Document ID {doc_id} not found."))
        if r.status_code == 403:
            raise SystemExit(red(f"Document ID {doc_id} is private — you do not have access."))
        r.raise_for_status()
        return r.json()

    def download_version(self, doc_id: int, version_num: int, dest: Path) -> Path:
        """Download a specific version and save to dest (file or directory)."""
        r = self.get(f"/docs/{doc_id}/versions/{version_num}/download",
                     stream=True, timeout=120)
        if r.status_code == 404:
            raise SystemExit(red(f"Version {version_num} of document {doc_id} not found."))
        r.raise_for_status()

        # Determine filename from Content-Disposition or fallback
        cd = r.headers.get("Content-Disposition", "")
        filename = None
        if 'filename="' in cd:
            filename = cd.split('filename="')[1].rstrip('"').strip()
        if not filename:
            filename = f"doc{doc_id}_v{version_num}"

        out = dest / filename if dest.is_dir() else dest
        out.parent.mkdir(parents=True, exist_ok=True)

        total  = int(r.headers.get("Content-Length", 0))
        done   = 0
        with open(out, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        bar = _progress_bar(done, total)
                        print(f"\r  {bar}  {_fmt_size(done)}", end="", flush=True)
        if total:
            print()  # newline after progress
        return out


# ── Helpers ───────────────────────────────────────────────────────────────────

def _guess_mime(path: Path) -> str:
    import mimetypes
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def _fmt_size(n: int) -> str:
    if n < 1024:        return f"{n} B"
    if n < 1048576:     return f"{n/1024:.1f} KB"
    return f"{n/1048576:.1f} MB"


def _validate_file(path: Path, max_mb: int) -> None:
    if not path.exists():
        raise SystemExit(red(f"File not found: {path}"))
    if not path.is_file():
        raise SystemExit(red(f"Not a file: {path}"))
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        raise SystemExit(red(
            f"File {path.name} is {size_mb:.1f} MB — exceeds server limit of {max_mb} MB."
        ))


def _print_doc_row(doc: dict, show_versions: bool = False) -> None:
    rating = doc.get("overall_rating", "")
    icon   = RATING_ICONS.get(rating, "")
    ver    = doc.get("latest_version", 1)
    cat    = doc.get("category", "")
    name   = doc.get("name", "")
    owner  = doc.get("owner_name", "")
    upd    = (doc.get("uploaded_at") or "")[:16].replace("T", " ")
    priv   = dim("🔒 Private") if doc.get("is_private") else ""

    print(
        f"  {bold(str(doc['id']).rjust(4))}  "
        f"{cyan(cat[:14].ljust(14))}  "
        f"{name[:40].ljust(40)}  "
        f"v{ver}  "
        f"{owner[:16].ljust(16)}  "
        f"{dim(upd)}  "
        f"{icon} {priv}"
    )


def _progress_bar(done: int, total: int, width: int = 30) -> str:
    pct   = done / total if total else 0
    filled = int(width * pct)
    bar   = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct*100:.0f}%"


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_config(args: argparse.Namespace) -> None:
    """Save server URL and authenticate."""
    cfg = load_config()

    if args.show:
        if not cfg:
            print(yellow("No config saved yet."))
        else:
            print(bold("Saved OpenClaw config:"))
            print(f"  Server : {cfg.get('server', '—')}")
            print(f"  Email  : {cfg.get('email', '—')}")
            print(f"  Token  : {'set' if cfg.get('token') else 'not set'}")
        return

    server = args.server or cfg.get("server")
    if not server:
        server = input("OpenClaw server URL (e.g. http://192.168.1.50:8000): ").strip()

    email = args.email or cfg.get("email")
    if not email:
        email = input("Your OpenClaw email: ").strip()

    # Ping server first
    print(f"\nConnecting to {cyan(server)} …")
    client  = OpenClawClient(server)
    info    = client.ping()
    max_mb  = info.get("max_upload_mb", 200)
    print(green(f"✓ Connected to {info.get('app', 'OpenClaw')} [{info.get('env', '')}]  |  max upload: {max_mb} MB"))

    # Authenticate
    password = args.password or getpass.getpass(f"Password for {email}: ")
    token    = client.login(email, password)

    cfg.update({"server": server, "email": email, "token": token, "max_upload_mb": max_mb})
    save_config(cfg)
    print(green(f"✓ Logged in. Config saved to {CONFIG_PATH}"))


def cmd_ping(args: argparse.Namespace) -> None:
    """Check server connectivity."""
    cfg    = load_config()
    server = args.server or cfg.get("server")
    if not server:
        raise SystemExit(red("No server configured. Run: python openclaw-upload.py config --server <URL>"))

    print(f"Pinging {cyan(server)} …")
    client = OpenClawClient(server)
    info   = client.ping()
    print(green("✓ Server reachable"))
    print(f"  App     : {info.get('app')}")
    print(f"  Version : {info.get('version')}")
    print(f"  Env     : {info.get('env')}")
    print(f"  Max upload : {info.get('max_upload_mb')} MB")
    print(f"  Categories : {', '.join(info.get('categories', []))}")


def cmd_upload(args: argparse.Namespace) -> None:
    """Upload one or more files to OpenClaw."""
    cfg    = require_config()
    client = OpenClawClient(cfg["server"], cfg["token"])
    max_mb = cfg.get("max_upload_mb", 200)

    files = [Path(f) for f in args.file]

    # Validate all files before starting any upload
    for fp in files:
        _validate_file(fp, max_mb)

    # Category
    category = args.category
    if not category:
        print("\nAvailable categories:")
        for i, c in enumerate(VALID_CATEGORIES, 1):
            print(f"  {i}. {c}")
        while True:
            try:
                choice = int(input("Select category number: ").strip())
                category = VALID_CATEGORIES[choice - 1]
                break
            except (ValueError, IndexError):
                print(red("Invalid choice — enter a number from the list"))

    # Multi-file upload
    results = []
    for i, fp in enumerate(files, 1):
        # Document name — use arg if one file, else filename-based
        if args.name and len(files) == 1:
            name = args.name
        else:
            name = args.name_prefix + fp.stem if args.name_prefix else fp.stem.replace("_", " ").replace("-", " ").title()

        size_str = _fmt_size(fp.stat().st_size)
        print(f"\n[{i}/{len(files)}] Uploading {bold(fp.name)}  ({size_str})")
        print(f"  → Name     : {name}")
        print(f"  → Category : {category}")
        if args.note:
            print(f"  → Note     : {args.note}")
        if args.doc_id:
            print(f"  → Doc ID   : {args.doc_id} (new version)")
        if args.private:
            print(f"  → Visibility : Private")

        try:
            doc = client.upload_file(
                file_path=fp,
                name=name,
                category=category,
                description=args.description or "",
                change_note=args.note or "Uploaded via CLI",
                is_private=args.private,
                doc_id=args.doc_id if args.doc_id else None,
            )

            # Find the newly uploaded version
            version = next(
                (v for v in (doc.get("versions") or []) if v.get("is_latest")),
                None
            )
            version_id = version["id"] if version else None

            print(green(f"  ✓ Uploaded  — Doc ID: {doc['id']}  Version: {doc.get('latest_version', 1)}"))
            if version_id:
                print(f"  ↳ Version ID: {version_id}  |  {_fmt_size(version.get('size_bytes', 0))}")

            # Trigger complexity analysis for Requirements and Design docs
            if args.analyse and category in ("Requirements", "Design") and version_id:
                print(f"  ⟳ Complexity analysis queued …")
                client.trigger_complexity(version_id)

            results.append({"file": str(fp), "doc_id": doc["id"], "version_id": version_id, "ok": True})

        except SystemExit:
            raise
        except Exception as exc:
            print(red(f"  ✕ Failed: {exc}"))
            results.append({"file": str(fp), "ok": False, "error": str(exc)})

    # Summary
    ok      = sum(1 for r in results if r["ok"])
    failed  = len(results) - ok
    print(f"\n{'─'*50}")
    print(bold(f"Upload complete: {green(str(ok))} succeeded, {red(str(failed)) if failed else '0'} failed"))
    if ok > 0:
        print(f"View at: {cyan(cfg['server'].replace(':8000', ':3000') + '/#documents')}")


def cmd_list(args: argparse.Namespace) -> None:
    """List documents on the OpenClaw server."""
    cfg    = require_config()
    client = OpenClawClient(cfg["server"], cfg["token"])

    category = args.category
    print(f"\nFetching documents from {cyan(cfg['server'])} …")
    docs = client.list_docs(category)

    if not docs:
        print(yellow("No documents found."))
        return

    print(f"\n{bold('ID'.rjust(6))}  {'Category'.ljust(14)}  {'Name'.ljust(40)}  Ver  {'Owner'.ljust(16)}  {'Updated'}")
    print("─" * 110)
    for doc in docs:
        _print_doc_row(doc)

    print(f"\n{len(docs)} document(s)  |  Server: {cfg['server']}")


def cmd_status(args: argparse.Namespace) -> None:
    """Check complexity analysis status for a version."""
    cfg    = require_config()
    client = OpenClawClient(cfg["server"], cfg["token"])

    result = client.get_complexity(args.version_id)
    if not result:
        print(yellow(f"No complexity analysis found for version_id={args.version_id}"))
        print(f"Run:  python openclaw-upload.py analyse --version-id {args.version_id}")
        return

    status = result.get("analyse_status", "unknown")
    rating = result.get("overall_rating", "—")
    icon   = RATING_ICONS.get(rating, "")
    score  = result.get("overall_score", 0)

    print(f"\n{bold(result.get('doc_name', '—'))}  v{result.get('version_number', '?')}")
    print(f"  Status  : {green('complete') if status == 'complete' else yellow(status)}")
    print(f"  Rating  : {icon} {rating}  (avg score: {score:.1f})")
    print(f"  Sections: {result.get('section_count', 0)}")

    if status == "complete" and result.get("sections"):
        print(f"\n  {'ID'.ljust(10)}  {'Title'.ljust(45)}  {'Rating'.ljust(10)}  Score")
        print("  " + "─" * 80)
        for sec in result["sections"]:
            icon2 = RATING_ICONS.get(sec["rating"], " ")
            print(
                f"  {sec['section_id'].ljust(10)}  "
                f"{sec['title'][:44].ljust(45)}  "
                f"{icon2} {sec['rating'].ljust(8)}  "
                f"{sec['score']}"
            )


def cmd_analyse(args: argparse.Namespace) -> None:
    """Trigger complexity analysis for a specific version."""
    cfg    = require_config()
    client = OpenClawClient(cfg["server"], cfg["token"])
    client.trigger_complexity(args.version_id)
    print(green(f"✓ Complexity analysis queued for version_id={args.version_id}"))
    print(f"Check status: python openclaw-upload.py status --version-id {args.version_id}")


def cmd_download(args: argparse.Namespace) -> None:
    """Download a document (or specific version) from the OpenClaw server."""
    cfg    = require_config()
    client = OpenClawClient(cfg["server"], cfg["token"])

    doc = client.get_doc(args.doc_id)

    # Resolve which version to download
    if args.version:
        version_num = args.version
        ver_meta = next((v for v in doc["versions"] if v["version_number"] == version_num), None)
        if not ver_meta:
            raise SystemExit(red(f"Version {version_num} not found for document ID {args.doc_id}."))
    else:
        version_num = doc["latest_version"]
        ver_meta = next((v for v in doc["versions"] if v["version_number"] == version_num), None)

    dest = Path(args.output).expanduser().resolve() if args.output else Path.cwd()

    print(f"\nDownloading  {bold(doc['name'])}  "
          f"v{version_num}  ({doc['category']})  "
          f"{_fmt_size(ver_meta['size_bytes'] if ver_meta else 0)}")
    print(f"To: {dest}")

    out = client.download_version(args.doc_id, version_num, dest)

    print(green(f"✓ Saved: {out}"))


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openclaw-upload",
        description="OpenClaw document upload CLI — send files from your machine to a remote OpenClaw server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First-time setup
  python openclaw-upload.py config --server http://192.168.1.50:8000 --email dev@team.com

  # Upload a single file
  python openclaw-upload.py upload --file ./requirements.pdf --category Requirements

  # Upload multiple files
  python openclaw-upload.py upload --file ./req.pdf ./design.docx --category Design

  # Upload as new version of doc ID 12, trigger complexity analysis automatically
  python openclaw-upload.py upload --file ./req_v2.pdf --doc-id 12 --note "Added auth section" --analyse

  # List all documents
  python openclaw-upload.py list

  # List only Requirements documents
  python openclaw-upload.py list --category Requirements

  # Check complexity result for a version
  python openclaw-upload.py status --version-id 5
        """,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── config ──
    p_cfg = sub.add_parser("config", help="Configure server URL and login credentials")
    p_cfg.add_argument("--server",   help="OpenClaw server URL, e.g. http://192.168.1.50:8000")
    p_cfg.add_argument("--email",    help="Your OpenClaw email address")
    p_cfg.add_argument("--password", help="Your password (omit to be prompted securely)")
    p_cfg.add_argument("--show",     action="store_true", help="Show current saved config")

    # ── ping ──
    p_ping = sub.add_parser("ping", help="Test connection to OpenClaw server")
    p_ping.add_argument("--server", help="Override server URL")

    # ── upload ──
    p_up = sub.add_parser("upload", help="Upload one or more documents")
    p_up.add_argument("--file",        nargs="+", required=True, metavar="PATH", help="File(s) to upload")
    p_up.add_argument("--category",    choices=VALID_CATEGORIES,                 help="Document category")
    p_up.add_argument("--name",        help="Document name (single-file uploads only)")
    p_up.add_argument("--name-prefix", help="Prefix for auto-generated names in multi-file uploads")
    p_up.add_argument("--description", help="Short description of the document")
    p_up.add_argument("--note",        help="Change note (what changed in this version)")
    p_up.add_argument("--doc-id",      type=int, metavar="ID", help="Upload as new version of this document ID")
    p_up.add_argument("--private",     action="store_true",    help="Make document private (visible only to you)")
    p_up.add_argument("--analyse",     action="store_true",    help="Trigger complexity analysis after upload (Requirements/Design only)")

    # ── list ──
    p_ls = sub.add_parser("list", help="List documents on the server")
    p_ls.add_argument("--category", choices=VALID_CATEGORIES, help="Filter by category")

    # ── status ──
    p_st = sub.add_parser("status", help="Show complexity analysis result for a version")
    p_st.add_argument("--version-id", type=int, required=True, metavar="ID", help="Document version ID")

    # ── analyse ──
    p_an = sub.add_parser("analyse", help="Trigger complexity analysis for a document version")
    p_an.add_argument("--version-id", type=int, required=True, metavar="ID", help="Document version ID")

    # ── download ──
    p_dl = sub.add_parser(
        "download",
        help="Download a document from the server to your local machine",
        description="Download a document (latest version by default) from the OpenClaw server.",
    )
    p_dl.add_argument("--doc-id",  type=int, required=True, metavar="ID",  help="Document ID (from 'list' command)")
    p_dl.add_argument("--version", type=int, metavar="N",                  help="Version number to download (default: latest)")
    p_dl.add_argument("--output",  metavar="DIR",                          help="Destination folder (default: current directory)")

    return parser


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    dispatch = {
        "config":   cmd_config,
        "ping":     cmd_ping,
        "upload":   cmd_upload,
        "list":     cmd_list,
        "status":   cmd_status,
        "analyse":  cmd_analyse,
        "download": cmd_download,
    }

    try:
        dispatch[args.command](args)
    except KeyboardInterrupt:
        print(f"\n{yellow('Cancelled.')}")
        sys.exit(0)


if __name__ == "__main__":
    main()
