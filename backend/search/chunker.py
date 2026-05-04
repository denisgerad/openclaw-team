"""
openclaw/backend/search/chunker.py

Splits extracted document text into chunks suitable for embedding.

Strategy:
  - Split on paragraph / double-newline boundaries first
  - If a paragraph exceeds MAX_TOKENS, split further on sentences
  - Overlap: each chunk includes a small tail from the previous chunk
    so searches near chunk boundaries still find relevant content

Chunk metadata stored alongside each chunk:
  doc_id, version_number, chunk_index, page_hint (if available)

These are stored in ChromaDB alongside the embedding.
"""
import re
from dataclasses import dataclass


MAX_CHARS    = 1200   # ~300 tokens at ~4 chars/token — safe for Mistral embed
OVERLAP_CHARS = 150   # overlap between consecutive chunks


@dataclass
class Chunk:
    text:         str
    chunk_index:  int
    char_start:   int
    char_end:     int
    page_hint:    int | None = None   # extracted from "[Page N]" markers


def chunk_text(text: str) -> list[Chunk]:
    """
    Split text into overlapping chunks.
    Returns list of Chunk objects, each with position metadata.
    """
    if not text.strip():
        return []

    # Extract page markers added by the PDF extractor
    # "[Page 3]\n..." → track which page each paragraph came from
    page_map: dict[int, int] = {}   # char_offset → page_number
    clean_lines = []
    current_page = None
    pos = 0

    for line in text.split("\n"):
        m = re.match(r"^\[Page (\d+)\]$", line.strip())
        if m:
            current_page = int(m.group(1))
        else:
            if current_page is not None:
                page_map[pos] = current_page
            clean_lines.append(line)
            pos += len(line) + 1   # +1 for \n

    clean_text = "\n".join(clean_lines)

    # Split on paragraph breaks
    paragraphs = re.split(r"\n{2,}", clean_text)

    # Build raw segments — split long paragraphs on sentence boundaries
    segments: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= MAX_CHARS:
            segments.append(para)
        else:
            # Split on sentence endings
            sentences = re.split(r"(?<=[.!?])\s+", para)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) + 1 <= MAX_CHARS:
                    current = f"{current} {sent}".strip() if current else sent
                else:
                    if current:
                        segments.append(current)
                    # Sentence itself too long — hard split
                    if len(sent) > MAX_CHARS:
                        for i in range(0, len(sent), MAX_CHARS - OVERLAP_CHARS):
                            segments.append(sent[i:i + MAX_CHARS])
                    else:
                        current = sent
            if current:
                segments.append(current)

    # Build chunks with overlap
    chunks: list[Chunk] = []
    tail = ""    # overlap tail from previous chunk
    char_pos = 0

    for i, seg in enumerate(segments):
        # Prepend overlap from previous chunk
        chunk_text = (tail + " " + seg).strip() if tail else seg
        start = max(0, char_pos - len(tail))
        end   = char_pos + len(seg)

        # Find nearest page hint
        page = None
        for offset in sorted(page_map.keys(), reverse=True):
            if offset <= char_pos:
                page = page_map[offset]
                break

        chunks.append(Chunk(
            text=chunk_text,
            chunk_index=i,
            char_start=start,
            char_end=end,
            page_hint=page,
        ))

        # Carry forward tail for overlap
        tail = seg[-OVERLAP_CHARS:] if len(seg) > OVERLAP_CHARS else seg
        char_pos = end + 2   # account for paragraph separator

    return chunks
