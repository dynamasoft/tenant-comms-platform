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
"""Unit tests for document loading, extraction, and chunking."""

from __future__ import annotations

import io

import pytest

from app import documents
from app.documents import (
    UnsupportedDocumentError,
    chunk_text,
    extract_text,
    extract_txt,
)


def test_extract_txt_roundtrip():
    text = "SECTION 1. RENT. Rent is $1500 per month."
    assert extract_txt(text.encode("utf-8")) == text


def test_extract_txt_tolerates_bad_bytes():
    # Invalid UTF-8 byte should be replaced, not raise.
    result = extract_txt(b"rent \xff due")
    assert "rent" in result and "due" in result


def test_extract_docx_roundtrip():
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("SECTION 5. UTILITIES.")
    document.add_paragraph("Tenant is responsible for all utilities as additional rent.")
    buffer = io.BytesIO()
    document.save(buffer)

    text = extract_text("lease.docx", buffer.getvalue())
    assert "UTILITIES" in text
    assert "additional rent" in text


def test_extract_text_dispatches_pdf(monkeypatch):
    """extract_text routes .pdf to the PDF extractor and reads from the byte buffer."""

    class _FakePage:
        def extract_text(self):
            return "SECTION 2. RENT. $1850 due on the first."

    class _FakeReader:
        def __init__(self, stream):
            # Must be constructed from a BytesIO of our bytes (in-memory, no disk).
            assert isinstance(stream, io.BytesIO)
            self.pages = [_FakePage(), _FakePage()]

    monkeypatch.setattr(documents, "PdfReader", _FakeReader, raising=False)
    # Patch the name used inside extract_pdf (imported locally), via the module import site.
    import pypdf

    monkeypatch.setattr(pypdf, "PdfReader", _FakeReader)

    text = extract_text("lease.pdf", b"%PDF-1.4 fake bytes")
    assert "RENT" in text
    assert text.count("SECTION 2") == 2  # two pages joined


def test_unsupported_extension_raises():
    with pytest.raises(UnsupportedDocumentError):
        extract_text("lease.rtf", b"data")


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n  \n") == []


def test_chunk_text_produces_multiple_chunks():
    # Build text well beyond one target chunk (~90 words).
    paragraphs = [f"Section {i}. This clause number {i} states an obligation." for i in range(40)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, target_words=30, overlap_words=5)
    assert len(chunks) > 1
    # Every chunk has content and none is absurdly long.
    for c in chunks:
        assert c.strip()
        assert len(c.split()) <= 60


def test_chunk_text_splits_one_huge_paragraph():
    words = " ".join(f"w{i}" for i in range(300))
    chunks = chunk_text(words, target_words=50, overlap_words=10)
    assert len(chunks) > 1
