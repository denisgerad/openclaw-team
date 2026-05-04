"""
openclaw/backend/search/summariser.py

Mistral-powered summarisation and comparison.

Three entry points:
  summarise_chunks()  — summarise a list of text chunks into a coherent summary
  summarise_document()— high-level summary of a full document version
  compare_versions()  — semantic diff between two document versions

All functions return plain strings.
Fall back to structured concatenation if Mistral API key not set.
"""
import logging

logger = logging.getLogger("openclaw.search.summariser")

# Max characters of text to send to Mistral in one call
# mistral-small context: 32k tokens ~ 128k chars — we stay well under
MAX_CONTEXT_CHARS = 24_000


def _call_mistral(prompt: str, system: str, api_key: str, max_tokens: int = 600) -> str:
    """Internal helper — one Mistral chat completion call."""
    if not api_key:
        return "[Mistral API key not configured — summary unavailable]"
    try:
        from mistralai import Mistral
        client   = Mistral(api_key=api_key)
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error(f"[summariser] Mistral call failed: {exc}")
        return f"[Summary unavailable: {exc}]"


# ── Summarise search results ───────────────────────────────────────────────────

def summarise_chunks(
    query:   str,
    chunks:  list[dict],   # list of search result dicts from chroma_store.search()
    api_key: str,
) -> str:
    """
    Synthesise a direct answer to `query` from the top matching chunks.
    Used to answer the "what does the documentation say about X?" question.
    """
    if not chunks:
        return "No relevant content found for this query."

    # Build context from top chunks
    context_parts = []
    total_chars   = 0
    for r in chunks:
        source = f"[{r['doc_name']} v{r['version_number']} — {r['filename']}"
        if r.get("page_hint"):
            source += f", page {r['page_hint']}"
        source += "]"
        entry  = f"{source}\n{r['text']}"
        if total_chars + len(entry) > MAX_CONTEXT_CHARS:
            break
        context_parts.append(entry)
        total_chars += len(entry)

    context = "\n\n---\n\n".join(context_parts)
    prompt  = (
        f"Based on the following document excerpts, answer this question:\n"
        f'"{query}"\n\n'
        f"DOCUMENT EXCERPTS:\n{context}\n\n"
        f"Provide a clear, structured answer citing which documents the information comes from. "
        f"If the excerpts don't fully answer the question, say so."
    )
    return _call_mistral(
        prompt=prompt,
        system="You are a technical document analyst. Synthesise precise answers from document excerpts. Always cite sources.",
        api_key=api_key,
        max_tokens=800,
    )


# ── Summarise a single document version ───────────────────────────────────────

def summarise_document(
    doc_name:       str,
    version_number: int,
    filename:       str,
    full_text:      str,
    api_key:        str,
) -> str:
    """
    Produce a structured summary of a complete document.
    Truncates input to MAX_CONTEXT_CHARS if needed.
    """
    text = full_text[:MAX_CONTEXT_CHARS]
    if len(full_text) > MAX_CONTEXT_CHARS:
        text += "\n\n[... document truncated for summary ...]"

    prompt = (
        f"Document: {doc_name} (version {version_number}, file: {filename})\n\n"
        f"CONTENT:\n{text}\n\n"
        f"Provide a structured summary with these sections:\n"
        f"1. PURPOSE — What is this document for?\n"
        f"2. KEY POINTS — Main points, decisions, or findings (bullet list)\n"
        f"3. SCOPE — What does this document cover / not cover?\n"
        f"4. ACTION ITEMS — Any tasks, deadlines, or owners mentioned\n"
        f"5. OPEN QUESTIONS — Any unresolved items or gaps\n\n"
        f"Be concise. Use bullet points where appropriate."
    )
    return _call_mistral(
        prompt=prompt,
        system="You are a senior technical analyst. Produce clear, structured document summaries for engineering teams.",
        api_key=api_key,
        max_tokens=1000,
    )


# ── Compare two document versions ─────────────────────────────────────────────

def compare_versions(
    doc_name:    str,
    v1_number:   int,
    v1_filename: str,
    v1_text:     str,
    v2_number:   int,
    v2_filename: str,
    v2_text:     str,
    api_key:     str,
) -> dict:
    """
    Semantic comparison between two versions of the same document.

    Returns dict:
      {
        "summary":   str   — high-level diff narrative
        "added":     str   — content/topics in v2 not in v1
        "removed":   str   — content/topics in v1 not in v2
        "changed":   str   — areas that changed significantly
        "unchanged": str   — areas that appear stable
        "verdict":   str   — overall assessment (minor update / major revision / etc.)
      }
    """
    # Truncate each to half the budget so both fit
    half = MAX_CONTEXT_CHARS // 2
    t1   = v1_text[:half] + ("\n[truncated]" if len(v1_text) > half else "")
    t2   = v2_text[:half] + ("\n[truncated]" if len(v2_text) > half else "")

    prompt = (
        f"Document: {doc_name}\n\n"
        f"VERSION {v1_number} ({v1_filename}):\n{t1}\n\n"
        f"{'='*60}\n\n"
        f"VERSION {v2_number} ({v2_filename}):\n{t2}\n\n"
        f"Perform a semantic comparison. Respond ONLY with valid JSON in this exact shape:\n"
        f'{{\n'
        f'  "summary":   "2-3 sentence overview of what changed",\n'
        f'  "added":     "topics or content present in v{v2_number} but not v{v1_number}",\n'
        f'  "removed":   "topics or content in v{v1_number} that are gone in v{v2_number}",\n'
        f'  "changed":   "areas that changed significantly between versions",\n'
        f'  "unchanged": "areas that appear consistent across both versions",\n'
        f'  "verdict":   "one of: Minor update / Moderate revision / Major revision / Complete rewrite"\n'
        f'}}'
    )

    raw = _call_mistral(
        prompt=prompt,
        system=(
            "You are a technical documentation analyst. "
            "Compare document versions semantically — focus on meaning and intent, not line-by-line diffs. "
            "Return only valid JSON, no markdown fences."
        ),
        api_key=api_key,
        max_tokens=900,
    )

    # Parse JSON response
    import json, re
    try:
        # Strip any accidental markdown fences
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(cleaned)
    except Exception:
        # Fallback if Mistral returns non-JSON
        return {
            "summary":   raw,
            "added":     "—",
            "removed":   "—",
            "changed":   "—",
            "unchanged": "—",
            "verdict":   "Unknown",
        }
