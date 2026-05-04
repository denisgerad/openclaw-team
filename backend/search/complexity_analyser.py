"""
openclaw/backend/search/complexity_analyser.py

Mistral-powered complexity analyser for Requirements and Design documents.

Pipeline:
  1. Extract full text from document version (reuses extractor.py)
  2. Split into logical sections (requirement/design entries)
  3. For each section: call Mistral with structured prompt
  4. Parse structured JSON response: rating, score, factors, evidence, confidence
  5. Compute document-level rollup (overall rating, factor frequency)
  6. Persist results to complexity_results + complexity_factors tables

Complexity bands:
  Simple   0-2 factors  → score 1-2
  Moderate 3-4 factors  → score 3-4
  Complex  5-6 factors  → score 5-6
  Critical 7+  factors  → score 7+

Section detection:
  Looks for patterns like "REQ-001", "DES-003", numbered headings,
  or double-newline separated blocks with a heading-like first line.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("openclaw.search.complexity")

# ── Rating thresholds ─────────────────────────────────────────────────────────
RATING_MAP = {
    "Simple":   (0, 2),
    "Moderate": (3, 4),
    "Complex":  (5, 6),
    "Critical": (7, 99),
}

RATING_COLORS = {
    "Simple":   "#00d68f",
    "Moderate": "#f5c400",
    "Complex":  "#ff8c00",
    "Critical": "#ff3b3b",
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ComplexityFactor:
    factor:      str           # e.g. "Real-time WebSocket protocol"
    category:    str           # e.g. "Concurrency & Performance"
    weight:      int           # 1-3  (1=minor, 2=significant, 3=critical)
    evidence:    str           # quoted phrase from document that drove this factor


@dataclass
class SectionResult:
    section_id:   str          # e.g. "REQ-007" or "DES-005"
    title:        str          # e.g. "Real-Time Activity Feed via WebSocket"
    rating:       str          # Simple | Moderate | Complex | Critical
    score:        int          # raw factor count
    confidence:   float        # 0.0-1.0
    summary:      str          # 1-2 sentence Mistral explanation
    factors:      list[ComplexityFactor] = field(default_factory=list)
    raw_text:     str = ""     # original section text (for UI drill-down)


@dataclass
class DocumentComplexityResult:
    doc_id:         int
    version_id:     int
    doc_name:       str
    version_number: int
    filename:       str
    category:       str        # Requirements | Design | etc.
    overall_rating: str
    overall_score:  float      # mean score across sections
    section_count:  int
    analysed_at:    datetime
    sections:       list[SectionResult] = field(default_factory=list)
    factor_summary: dict = field(default_factory=dict)  # factor_category → count


# ── Section splitter ──────────────────────────────────────────────────────────

# Patterns that indicate a new section heading
_SECTION_PATTERNS = [
    r"^(REQ-\d+)\s+(.+)",          # REQ-001 Title
    r"^(DES-\d+)\s+(.+)",          # DES-001 Title
    r"^(\d+\.\d+)\s+(.+)",         # 2.3 Title
    r"^(Section\s+\d+[.:]\s*.+)",  # Section 3: Title
]
_SECTION_RE = re.compile("|".join(_SECTION_PATTERNS), re.MULTILINE)

# Minimum chars for a section to be worth analysing
MIN_SECTION_CHARS = 80
MAX_SECTION_CHARS = 3000


def split_into_sections(text: str) -> list[tuple[str, str, str]]:
    """
    Split document text into (section_id, title, body) tuples.
    Falls back to paragraph-based splitting if no IDs found.

    Returns list of (id, title, body) where id may be "S1", "S2"... for fallback.
    """
    sections = []
    matches  = list(_SECTION_RE.finditer(text))

    if len(matches) >= 2:
        # Use matched section boundaries
        for i, m in enumerate(matches):
            start = m.start()
            end   = matches[i+1].start() if i+1 < len(matches) else len(text)
            body  = text[start:end].strip()

            # Extract id and title from the first matching group
            groups = [g for g in m.groups() if g]
            sec_id = groups[0] if groups else f"S{i+1}"
            title  = groups[1] if len(groups) > 1 else body.split("\n")[0][:80]
            title  = title.strip()

            # Skip metadata label rows (e.g. "Category:", "Date:")
            if title.endswith(":") or title.lower() in ("category", "date", "status", "priority"):
                continue

            if len(body) >= MIN_SECTION_CHARS:
                sections.append((sec_id, title, body[:MAX_SECTION_CHARS]))
    else:
        # Fallback: split on double newlines, treat first line as title
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        for i, para in enumerate(paragraphs):
            if len(para) < MIN_SECTION_CHARS:
                continue
            lines = para.split("\n")
            title = lines[0][:80]
            body  = para[:MAX_SECTION_CHARS]
            sections.append((f"S{i+1}", title, body))

    return sections[:30]   # hard cap — no doc should need more than 30 sections


# ── Mistral prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior software architect specialising in complexity assessment for engineering teams.

Your task is to analyse a requirement or design section and classify its implementation complexity.

Complexity bands:
  Simple   (score 1-2):  Standard CRUD, single table, no external dependencies, junior-capable
  Moderate (score 3-4):  Background processing, cross-entity logic, 1-2 integrations, experienced developer needed
  Complex  (score 5-6):  Real-time systems, multiple integrations, concurrency, senior developer + design review needed
  Critical (score 7+):   Distributed systems, compliance, cryptography, ML pipelines, architect review mandatory

Complexity factor categories (use these exact category names):
  - Algorithm & Logic
  - Interface & Integration
  - Data Complexity
  - Concurrency & Performance
  - Security & Compliance
  - UI & UX Complexity
  - Dependency & Environment
  - Testing & Verification

Respond ONLY with valid JSON, no markdown fences, no commentary outside the JSON."""

def _build_prompt(section_id: str, title: str, body: str) -> str:
    return f"""Analyse this requirement/design section for implementation complexity:

SECTION ID: {section_id}
TITLE: {title}

CONTENT:
{body}

Respond with this exact JSON structure:
{{
  "rating": "Simple | Moderate | Complex | Critical",
  "score": <integer 1-10, number of significant complexity factors>,
  "confidence": <float 0.0-1.0, how confident you are in this rating>,
  "summary": "<1-2 sentence explanation of why this rating was assigned>",
  "factors": [
    {{
      "factor": "<specific complexity factor name>",
      "category": "<one of the 8 categories above>",
      "weight": <1|2|3>,
      "evidence": "<brief quote or reference from the section that drives this factor>"
    }}
  ]
}}

Rules:
- score = number of distinct complexity factors found (not the sum of weights)
- Each factor must map to exactly one category
- Evidence must be a brief phrase actually from the section (max 15 words)
- If no complexity factors found, return score=1, rating=Simple, empty factors array
- Do not invent factors not supported by the text"""


# ── Mistral call ──────────────────────────────────────────────────────────────

def _call_mistral(prompt: str, api_key: str, retries: int = 2) -> dict | None:
    """Call Mistral and parse JSON response. Returns None on failure."""
    if not api_key:
        return None

    from mistralai import Mistral
    client = Mistral(api_key=api_key)

    for attempt in range(retries + 1):
        try:
            resp = client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=800,
                temperature=0.1,   # low temp for consistent structured output
            )
            raw = resp.choices[0].message.content.strip()
            # Strip accidental markdown fences
            raw = re.sub(r"```(?:json)?|```", "", raw).strip()
            return json.loads(raw)

        except json.JSONDecodeError:
            if attempt < retries:
                logger.warning(f"[complexity] JSON parse failed attempt {attempt+1} — retrying")
                continue
            logger.error("[complexity] All retry attempts failed — JSON malformed")
            return None
        except Exception as exc:
            logger.error(f"[complexity] Mistral call failed: {exc}")
            return None
    return None


# ── Score → rating normalisation ──────────────────────────────────────────────

def _score_to_rating(score: int) -> str:
    for rating, (lo, hi) in RATING_MAP.items():
        if lo <= score <= hi:
            return rating
    return "Critical"


def _fallback_section(section_id: str, title: str, body: str) -> SectionResult:
    """Used when Mistral is unavailable or returns malformed output."""
    return SectionResult(
        section_id=section_id,
        title=title,
        rating="Unknown",
        score=0,
        confidence=0.0,
        summary="Analysis unavailable — Mistral API not configured or returned invalid output.",
        factors=[],
        raw_text=body,
    )


# ── Main analysis function ────────────────────────────────────────────────────

async def analyse_document(
    doc_id:         int,
    version_id:     int,
    doc_name:       str,
    version_number: int,
    filename:       str,
    category:       str,
    file_path:      str,
    mime_type:      str,
    api_key:        str,
) -> DocumentComplexityResult:
    """
    Full document complexity analysis pipeline.
    Extracts text, splits sections, analyses each, returns DocumentComplexityResult.
    """
    from backend.search.extractor import extract_text

    # Extract text
    text = extract_text(path=file_path, mime_type=mime_type)
    if not text.strip():
        logger.warning(f"[complexity] No text extracted from {filename}")
        return DocumentComplexityResult(
            doc_id=doc_id, version_id=version_id, doc_name=doc_name,
            version_number=version_number, filename=filename, category=category,
            overall_rating="Unknown", overall_score=0.0, section_count=0,
            analysed_at=datetime.now(timezone.utc),
        )

    # Split into sections
    sections_raw = split_into_sections(text)
    logger.info(f"[complexity] {len(sections_raw)} section(s) found in '{doc_name}' v{version_number}")

    section_results: list[SectionResult] = []

    for sec_id, title, body in sections_raw:
        logger.info(f"[complexity] Analysing {sec_id}: {title[:50]}")

        if not api_key:
            section_results.append(_fallback_section(sec_id, title, body))
            continue

        prompt = _build_prompt(sec_id, title, body)
        parsed = _call_mistral(prompt, api_key)

        if not parsed:
            section_results.append(_fallback_section(sec_id, title, body))
            continue

        # Build factor objects
        factors = []
        for f in parsed.get("factors", []):
            factors.append(ComplexityFactor(
                factor=f.get("factor", ""),
                category=f.get("category", "Other"),
                weight=int(f.get("weight", 1)),
                evidence=f.get("evidence", ""),
            ))

        score  = int(parsed.get("score", 1))
        rating = parsed.get("rating") or _score_to_rating(score)

        # Validate rating is in allowed set
        if rating not in RATING_MAP:
            rating = _score_to_rating(score)

        section_results.append(SectionResult(
            section_id=sec_id,
            title=title,
            rating=rating,
            score=score,
            confidence=float(parsed.get("confidence", 0.8)),
            summary=parsed.get("summary", ""),
            factors=factors,
            raw_text=body,
        ))

    # ── Document-level rollup ─────────────────────────────────────────────────
    if not section_results:
        overall_score  = 0.0
        overall_rating = "Unknown"
    else:
        scored = [s for s in section_results if s.rating != "Unknown"]
        if scored:
            overall_score  = round(sum(s.score for s in scored) / len(scored), 1)
            overall_rating = _score_to_rating(int(overall_score))
        else:
            overall_score  = 0.0
            overall_rating = "Unknown"

    # Factor frequency across document
    factor_summary: dict[str, int] = {}
    for sec in section_results:
        for f in sec.factors:
            factor_summary[f.category] = factor_summary.get(f.category, 0) + 1

    return DocumentComplexityResult(
        doc_id=doc_id,
        version_id=version_id,
        doc_name=doc_name,
        version_number=version_number,
        filename=filename,
        category=category,
        overall_rating=overall_rating,
        overall_score=overall_score,
        section_count=len(section_results),
        analysed_at=datetime.now(timezone.utc),
        sections=section_results,
        factor_summary=factor_summary,
    )
