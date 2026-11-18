"""
Integration tests for Resume Management, Knowledge Base CRUD & BM25 search,
malicious upload rejection at the HTTP boundary, and demonstrable retrieval
impact on AI answer generation.
"""
import io
from pathlib import Path
from typing import AsyncIterator

import docx
import pytest

from app.core.config import settings
from app.services.answer_generation.base import LLMProvider
from app.services.answer_generation.context_manager import ContextManager
from app.services.answer_generation.service import AnswerGenerationService
from tests.conftest import TestAsyncSessionLocal


def _docx_bytes(lines: list[str]) -> bytes:
    d = docx.Document()
    for line in lines:
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


class ContextEchoLLM(LLMProvider):
    """Test LLM that synthesizes answers strictly from injected prompt facts so tests verify grounding."""

    def __init__(self):
        self.last_system_prompt = ""
        self.last_user_prompt = ""

    @property
    def name(self) -> str:
        return "echo-llm"

    @property
    def model_name(self) -> str:
        return "echo-v1"

    async def stream_generate(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 800, temperature: float = 0.3
    ) -> AsyncIterator[str]:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        if "SU53" in user_prompt and "PFCG" in user_prompt:
            yield "Based on your SAP Security notes, PFCG builds authorization roles and SU53 troubleshoots failed checks."
        elif "Enterprise SAP GRC Access Control" in user_prompt:
            yield "In your Enterprise SAP GRC Access Control project, you automated SoD risk checks."
        elif "MISSING PERSONAL CONTEXT DETECTED" in system_prompt:
            yield "[Needs customization — upload your resume for personalized details] Describe [Your Project]."
        else:
            yield "Generic answer without personal study notes."


@pytest.mark.asyncio
async def test_resume_upload_preview_replace_and_delete(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))

    # Initially empty
    r0 = await client.get("/api/resume/")
    assert r0.status_code == 200
    assert r0.json()["has_resume"] is False

    # Upload first DOCX resume
    doc1 = _docx_bytes([
        "Skills",
        "Python, FastAPI, SAP Security, SQL",
        "Work Experience",
        "Security Analyst at AlphaTech (2023-2025)",
        "Projects",
        "Enterprise SAP GRC Access Control — Automated SoD reviews.",
        "Certifications",
        "AWS Solutions Architect",
    ])
    up1 = await client.post(
        "/api/resume/upload",
        files={
            "file": (
                "candidate_v1.docx",
                doc1,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert up1.status_code == 201
    body1 = up1.json()
    assert body1["filename"] == "candidate_v1.docx"
    assert "SAP Security" in body1["skills"]
    assert any("Enterprise SAP GRC Access Control" in p for p in body1["projects"])
    assert any("AWS Solutions Architect" in c for c in body1["certifications"])

    # Replace with v2 resume -> old file should be cleaned up
    resumes_dir = tmp_path / "resumes"
    assert len(list(resumes_dir.glob("*"))) == 1

    doc2 = _docx_bytes(["Skills", "Oracle Fusion HCM, OTBI, BI Publisher"])
    up2 = await client.post(
        "/api/resume/upload",
        files={
            "file": (
                "candidate_v2.docx",
                doc2,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert up2.status_code == 201
    body2 = up2.json()
    assert body2["filename"] == "candidate_v2.docx"
    assert "OTBI" in body2["skills"]
    assert len(list(resumes_dir.glob("*"))) == 1

    # Delete active resume -> removes DB row AND disk file
    del_resp = await client.delete(f"/api/resume/{body2['id']}")
    assert del_resp.status_code == 204
    assert len(list(resumes_dir.glob("*"))) == 0

    r_after = await client.get("/api/resume/")
    assert r_after.json()["has_resume"] is False


@pytest.mark.asyncio
async def test_kb_upload_search_and_answer_quality_improvement(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))

    # 1. Verify all 17 categories exposed
    cats = (await client.get("/api/knowledge-base/categories")).json()
    assert len(cats) == 17

    # Create a session for context testing
    s_id = (await client.post("/api/sessions/", json={"title": "KB Grounding Test", "type": "technical"})).json()["id"]
    cm = ContextManager()
    llm = ContextEchoLLM()
    svc = AnswerGenerationService(provider=llm)

    # 2. BEFORE uploading resume & KB -> personal question flagged & SAP answer is generic
    async with TestAsyncSessionLocal() as db:
        ctx_proj_before = await cm.build_context(db, s_id, "q1", "Explain your previous project.")
        ctx_sap_before = await cm.build_context(db, s_id, "q2", "Explain the SAP authorization concept.")

    assert ctx_proj_before.needs_customization is True
    assert ctx_sap_before.kb_excerpts == []
    ans_sap_before = await svc.generate_answer(ctx_sap_before)
    assert "Generic answer" in ans_sap_before.answer_text

    # 3. Upload Resume + SAP Security KB Markdown document
    resume_docx = _docx_bytes([
        "Skills",
        "SAP Security, Python, FastAPI",
        "Projects",
        "Enterprise SAP GRC Access Control — Automated SoD reviews.",
    ])
    assert (
        await client.post(
            "/api/resume/upload",
            files={
                "file": (
                    "resume.docx",
                    resume_docx,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    ).status_code == 201

    sap_md = b"# SAP Authorization\nSAP authorization uses PFCG roles, authorization objects, profiles, and SU53 for troubleshooting missing authorizations."
    kb_up = await client.post(
        "/api/knowledge-base/upload",
        data={"category": "SAP Security"},
        files={"file": ("sap_auth_notes.md", sap_md, "text/markdown")},
    )
    assert kb_up.status_code == 201
    doc_id = kb_up.json()["id"]
    assert kb_up.json()["category"] == "SAP Security"
    assert kb_up.json()["chunk_count"] >= 1

    # Search endpoint returns relevant excerpt
    search_resp = await client.get("/api/knowledge-base/search?q=SAP+authorization+PFCG+SU53")
    assert search_resp.status_code == 200
    hits = search_resp.json()
    assert len(hits) >= 1
    assert hits[0]["filename"] == "sap_auth_notes.md"
    assert "PFCG" in hits[0]["excerpt"]

    # 4. AFTER uploading Resume + KB -> answers demonstrably incorporate uploaded facts!
    async with TestAsyncSessionLocal() as db:
        ctx_proj_after = await cm.build_context(db, s_id, "q1", "Explain your previous project.")
        ctx_sap_after = await cm.build_context(db, s_id, "q2", "Explain the SAP authorization concept.")

    assert ctx_proj_after.needs_customization is False
    assert len(ctx_sap_after.kb_excerpts) >= 1
    assert "SU53" in ctx_sap_after.kb_excerpts[0]["excerpt"]

    ans_proj_after = await svc.generate_answer(ctx_proj_after)
    assert "Enterprise SAP GRC Access Control" in ans_proj_after.answer_text

    ans_sap_after = await svc.generate_answer(ctx_sap_after)
    assert "PFCG" in ans_sap_after.answer_text and "SU53" in ans_sap_after.answer_text

    # 5. Delete KB document cleans DB and disk
    assert (await client.delete(f"/api/knowledge-base/{doc_id}")).status_code == 204
    assert (await client.get(f"/api/knowledge-base/{doc_id}")).status_code == 404
    assert len(list((tmp_path / "uploads").glob("*"))) == 0


@pytest.mark.asyncio
async def test_http_rejects_malicious_uploads(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))

    # Wrong MIME
    r1 = await client.post(
        "/api/resume/upload",
        files={"file": ("resume.pdf", b"%PDF-1.4\nfake", "text/html")},
    )
    assert r1.status_code == 400

    # Malformed PDF
    r2 = await client.post(
        "/api/resume/upload",
        files={"file": ("broken.pdf", b"%PDF-1.4\nNOT_REAL_PDF_STRUCTURE", "application/pdf")},
    )
    assert r2.status_code == 400

    # Unsupported executable extension on KB upload
    r3 = await client.post(
        "/api/knowledge-base/upload",
        data={"category": "Cybersecurity"},
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/x-msdownload")},
    )
    assert r3.status_code == 400

    # Path traversal filename on KB upload
    r4 = await client.post(
        "/api/knowledge-base/upload",
        data={"category": "Cybersecurity"},
        files={"file": ("../../evil.txt", b"hello", "text/plain")},
    )
    assert r4.status_code == 400
