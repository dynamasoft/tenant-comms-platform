# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Lease document loading, text extraction, and chunking.

Supports PDF, DOCX, and TXT. Extraction works directly from in-memory bytes (a BytesIO
buffer) so an uploaded lease is never written to disk — see the README's privacy note.
"""

from __future__ import annotations

import io
from pathlib import Path

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")


class UnsupportedDocumentError(ValueError):
    """Raised when a file type we cannot parse is provided."""


def extract_pdf(data: bytes) -> str:
    """Extract text from PDF bytes."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n\n".join(pages)


def extract_docx(data: bytes) -> str:
    """Extract text from DOCX bytes."""
    from docx import Document

    document = Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


def extract_txt(data: bytes) -> str:
    """Decode plain-text bytes (UTF-8, tolerant of bad bytes)."""
    return data.decode("utf-8", errors="replace")


def extract_text(filename: str, data: bytes) -> str:
    """Extract text from an uploaded document, dispatching on the file extension.

    Args:
        filename: Original filename (used only for its extension).
        data: Raw file bytes.

    Returns:
        The extracted plain text (may be empty if the document has no extractable text,
        e.g. a scanned image PDF).

    Raises:
        UnsupportedDocumentError: If the extension is not one of .pdf/.docx/.txt.
    """
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(data)
    if suffix == ".docx":
        return extract_docx(data)
    if suffix == ".txt":
        return extract_txt(data)
    raise UnsupportedDocumentError(
        f"Unsupported file type '{suffix}'. Supported types: {', '.join(SUPPORTED_EXTENSIONS)}."
    )


def _normalize_paragraphs(text: str) -> list[str]:
    """Split text into non-empty, whitespace-collapsed paragraphs."""
    raw = text.replace("\r\n", "\n").split("\n")
    paragraphs: list[str] = []
    buffer: list[str] = []
    for line in raw:
        if line.strip():
            buffer.append(line.strip())
        elif buffer:
            paragraphs.append(" ".join(buffer))
            buffer = []
    if buffer:
        paragraphs.append(" ".join(buffer))
    return paragraphs


def chunk_text(text: str, target_words: int = 90, overlap_words: int = 15) -> list[str]:
    """Chunk lease text into overlapping, clause-sized passages for retrieval.

    Paragraphs are accumulated until a chunk reaches ~``target_words`` words; the last
    ``overlap_words`` words of a chunk are prepended to the next for context continuity.
    Deterministic (no randomness) so retrieval and tests are stable.

    Args:
        text: The full extracted lease text.
        target_words: Approximate words per chunk.
        overlap_words: Words of overlap carried between consecutive chunks.

    Returns:
        A list of chunk strings (empty list if the text has no content).
    """
    paragraphs = _normalize_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append(" ".join(current).strip())
            current = []
            current_len = 0

    for para in paragraphs:
        words = para.split()
        # A single very long paragraph is split across multiple chunks.
        if len(words) > target_words:
            flush()
            start = 0
            while start < len(words):
                window = words[start : start + target_words]
                chunks.append(" ".join(window).strip())
                start += max(1, target_words - overlap_words)
            continue
        if current_len + len(words) > target_words and current:
            # Carry an overlap tail into the next chunk.
            tail = " ".join(current).split()[-overlap_words:] if overlap_words else []
            flush()
            current = list(tail)
            current_len = len(tail)
        current.append(para)
        current_len += len(words)
    flush()
    return [c for c in chunks if c]
