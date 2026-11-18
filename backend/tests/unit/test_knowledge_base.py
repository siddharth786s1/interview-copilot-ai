"""
Unit tests for Knowledge Base chunker, BM25 retriever, structured resume extractor,
and defensive file parser (including malicious file rejection cases).
"""
import io
import zipfile

import docx
import pytest

from app.core.exceptions import ValidationError
from app.services.knowledge_base.chunker import KB_CATEGORIES, chunk_text
from app.services.knowledge_base.parser import (
    KB_EXTENSIONS,
    RESUME_EXTENSIONS,
    extract_document_text,
    sanitize_filename,
    validate_upload,
)
from app.services.knowledge_base.resume_extractor import extract_resume_fields
from app.services.knowledge_base.retriever import retrieve_from_chunks


def _make_docx_bytes(lines: list[str]) -> bytes:
    d = docx.Document()
    for line in lines:
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _make_minimal_pdf_bytes(text: str = "Hello SQL Injection Prevention") -> bytes:
    """Construct a minimal valid single-page PDF 1.4 with extractable Helvetica text."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        b"4 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def test_seventeen_kb_categories_present():
    assert len(KB_CATEGORIES) == 17
    for expected in ("SAP Security", "Oracle Fusion HCM", "OTBI", "BI Publisher", "OWASP", "System Design"):
        assert expected in KB_CATEGORIES


def test_chunk_text_creates_overlapping_chunks():
    text = ("Sentence about API security and OAuth2 token validation. " * 25).strip()
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) >= 4
    assert all(len(c["text"]) <= 350 for c in chunks)
    assert chunks[0]["chunk_index"] == 0


def test_bm25_retriever_ranks_relevant_documents_highest():
    corpus = [
        {
            "document_id": "d1",
            "filename": "sap_sec.md",
            "category": "SAP Security",
            "text": "SAP authorization relies on authorization objects, PFCG roles, profiles, and SU53 troubleshooting.",
        },
        {
            "document_id": "d2",
            "filename": "oracle_reporting.md",
            "category": "OTBI",
            "text": "OTBI provides real-time ad-hoc transactional analytics while BI Publisher handles pixel-perfect scheduled reports.",
        },
        {
            "document_id": "d3",
            "filename": "python_notes.txt",
            "category": "Python",
            "text": "Python asyncio uses an event loop to run coroutines concurrently on a single thread.",
        },
    ]

    sap_hits = retrieve_from_chunks("Explain the SAP authorization concept with PFCG", corpus, top_k=2)
    assert len(sap_hits) >= 1
    assert sap_hits[0]["document_id"] == "d1"

    otbi_hits = retrieve_from_chunks("What is the difference between OTBI and BI Publisher?", corpus, top_k=2)
    assert len(otbi_hits) >= 1
    assert otbi_hits[0]["document_id"] == "d2"

    # Unrelated query yields empty list rather than polluting context
    none_hits = retrieve_from_chunks("quantum thermodynamics banana", corpus, top_k=2)
    assert none_hits == []


def test_resume_structured_extraction_does_not_fabricate():
    resume_text = """
    Jane Candidate
    Skills
    Python, FastAPI, SQL, SAP Security, OWASP
    Work Experience
    Senior Security Engineer at Acme Corp (2022-2026) — Led API security audits.
    Projects
    Zero-Trust Gateway — Built JWT & RBAC middleware in FastAPI.
    Education
    B.S. in Computer Science, State University
    """
    fields = extract_resume_fields(resume_text)
    assert "Python" in fields["skills"]
    assert "SAP Security" in fields["skills"]
    assert any("Acme Corp" in e for e in fields["experience"])
    assert any("Zero-Trust Gateway" in p for p in fields["projects"])
    assert any("Computer Science" in ed for ed in fields["education"])
    # No certifications in input -> must be empty, never fabricated
    assert fields["certifications"] == []


def test_valid_pdf_and_docx_parsing():
    pdf_bytes = _make_minimal_pdf_bytes("SAP Authorization Objects and PFCG Roles")
    name, ext = validate_upload("guide.pdf", "application/pdf", pdf_bytes, KB_EXTENSIONS, 1024 * 1024)
    assert ext == ".pdf"
    extracted = extract_document_text(ext, pdf_bytes)
    assert "PFCG Roles" in extracted

    docx_bytes = _make_docx_bytes(["Skills", "Python, SQL, OTBI"])
    name2, ext2 = validate_upload(
        "resume.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx_bytes,
        RESUME_EXTENSIONS,
        1024 * 1024,
    )
    assert ext2 == ".docx"
    extracted2 = extract_document_text(ext2, docx_bytes)
    assert "OTBI" in extracted2


def test_malicious_uploads_rejected():
    # 1. Oversized file
    with pytest.raises(ValidationError, match="maximum allowed size"):
        validate_upload("big.txt", "text/plain", b"A" * 2048, KB_EXTENSIONS, max_bytes=1024)

    # 2. Wrong MIME type
    with pytest.raises(ValidationError, match="MIME type"):
        validate_upload("evil.pdf", "text/html", b"%PDF-1.4...", RESUME_EXTENSIONS, max_bytes=1024 * 1024)

    # 3. Spoofed PDF header (HTML renamed to .pdf)
    with pytest.raises(ValidationError, match="valid PDF header"):
        validate_upload("spoof.pdf", "application/pdf", b"<html><script>alert(1)</script></html>", RESUME_EXTENSIONS, 1024 * 1024)

    # 4. Malformed PDF with valid header but garbage body
    with pytest.raises(ValidationError, match="Malformed|no readable|No extractable"):
        extract_document_text(".pdf", b"%PDF-1.4\n%%%CORRUPT_BINARY_JUNK_NOT_A_PDF%%%")

    # 5. Path traversal filenames
    for bad_name in ("../../etc/passwd.txt", "..\\windows\\win.ini.txt", "sub/dir/file.pdf", "a\x00b.pdf"):
        with pytest.raises(ValidationError):
            sanitize_filename(bad_name)

    # 6. Macro-enabled DOCX (vbaProject.bin)
    macro_buf = io.BytesIO()
    with zipfile.ZipFile(macro_buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document/>")
        zf.writestr("word/vbaProject.bin", b"FAKE_VBA_MACRO")
    with pytest.raises(ValidationError, match="Macro-enabled"):
        extract_document_text(".docx", macro_buf.getvalue())

    # 7. XXE injection inside DOCX XML
    xxe_buf = io.BytesIO()
    with zipfile.ZipFile(xxe_buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><w:document>&xxe;</w:document>',
        )
    with pytest.raises(ValidationError, match="DOCTYPE/ENTITY"):
        extract_document_text(".docx", xxe_buf.getvalue())
