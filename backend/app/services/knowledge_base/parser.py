"""
Defensive document validator and text extractor for PDF, DOCX, TXT, and Markdown files.

Security guarantees:
- Extension + MIME type + magic-byte validation
- Path traversal rejection and safe UUID-prefixed storage filenames
- File size enforcement
- DOCX macro (vbaProject.bin) and XXE (<!DOCTYPE / <!ENTITY) rejection
- Malformed PDF rejection
- Extracted text length cap (100,000 characters)
"""
import io
import os
import re
import uuid
import zipfile
from pathlib import Path
from typing import Set, Tuple

from app.core.exceptions import ValidationError

MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_KB_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_EXTRACTED_CHARS = 100_000

RESUME_EXTENSIONS: Set[str] = {".pdf", ".docx"}
KB_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt", ".md"}

ALLOWED_MIME_BY_EXT = {
    ".pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream"},
}


def sanitize_filename(raw_filename: str) -> str:
    """Validate and sanitize an uploaded filename, rejecting path traversal attempts."""
    if not raw_filename or "\x00" in raw_filename:
        raise ValidationError("Invalid filename.")

    if ".." in raw_filename or "/" in raw_filename or "\\" in raw_filename:
        raise ValidationError("Filename contains forbidden path characters.")

    cleaned = re.sub(r"[^a-zA-Z0-9._ -]", "_", raw_filename).strip()
    if not cleaned or cleaned.startswith("."):
        raise ValidationError("Invalid filename.")
    return cleaned[:180]


def validate_upload(
    filename: str,
    content_type: str | None,
    data: bytes,
    allowed_extensions: Set[str],
    max_bytes: int,
) -> Tuple[str, str]:
    """
    Validate filename, size, extension, MIME type, and file magic bytes.
    Returns (sanitized_filename, extension).
    """
    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()

    if ext not in allowed_extensions:
        allowed_str = ", ".join(sorted(allowed_extensions))
        raise ValidationError(f"Unsupported file type '{ext or 'none'}'. Allowed: {allowed_str}.")

    if not data:
        raise ValidationError("Uploaded file is empty.")

    if len(data) > max_bytes:
        limit_mb = round(max_bytes / (1024 * 1024), 1)
        raise ValidationError(f"File exceeds maximum allowed size of {limit_mb} MB.")

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime and mime not in ALLOWED_MIME_BY_EXT.get(ext, set()):
        raise ValidationError(f"MIME type '{mime}' is not allowed for '{ext}' files.")

    # Magic-byte verification for binary formats
    if ext == ".pdf":
        if not data.lstrip().startswith(b"%PDF-"):
            raise ValidationError("File content does not match a valid PDF header.")
    elif ext == ".docx":
        if not data.startswith(b"PK\x03\x04"):
            raise ValidationError("File content does not match a valid DOCX archive.")

    return safe_name, ext


def _extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if len(reader.pages) == 0:
            raise ValidationError("PDF contains no readable pages.")
        parts = []
        total_len = 0
        for page in reader.pages:
            txt = page.extract_text() or ""
            parts.append(txt)
            total_len += len(txt)
            if total_len >= MAX_EXTRACTED_CHARS:
                break
        text = "\n".join(parts).strip()
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Malformed or unreadable PDF document: {exc}") from exc

    if not text:
        raise ValidationError("No extractable text found in PDF document.")
    return text[:MAX_EXTRACTED_CHARS]


def _extract_docx_text(data: bytes) -> str:
    # Defensive ZIP & XML inspection BEFORE handing to python-docx
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            # Reject macros
            for name in names:
                lower = name.lower()
                if "vbaproject.bin" in lower or lower.endswith(".bin"):
                    raise ValidationError("Macro-enabled DOCX files are rejected for security.")
                if ".." in name or name.startswith("/") or name.startswith("\\"):
                    raise ValidationError("DOCX archive contains unsafe entry paths.")
                if lower.endswith(".xml") or lower.endswith(".rels"):
                    raw_xml = zf.read(name)
                    if b"<!DOCTYPE" in raw_xml or b"<!ENTITY" in raw_xml:
                        raise ValidationError("DOCX XML contains forbidden DOCTYPE/ENTITY declarations.")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Malformed DOCX archive: {exc}") from exc

    import docx

    try:
        doc = docx.Document(io.BytesIO(data))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        # Also read table cells (common in modern resumes)
        for table in doc.tables:
            for row in table.rows:
                row_vals = [cell.text.strip() for cell in row.cells if cell.text and cell.text.strip()]
                if row_vals:
                    paragraphs.append(" | ".join(row_vals))
        text = "\n".join(paragraphs).strip()
    except Exception as exc:
        raise ValidationError(f"Failed to parse DOCX content: {exc}") from exc

    if not text:
        raise ValidationError("No extractable text found in DOCX document.")
    return text[:MAX_EXTRACTED_CHARS]


def _extract_plain_text(data: bytes) -> str:
    # Reject binary payloads disguised as .txt / .md
    if b"\x00" in data[:4096]:
        raise ValidationError("Binary content is not allowed in text/markdown files.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("latin-1")
        except Exception as exc:
            raise ValidationError(f"Unable to decode text file: {exc}") from exc

    cleaned = text.strip()
    if not cleaned:
        raise ValidationError("Uploaded text document is empty.")
    return cleaned[:MAX_EXTRACTED_CHARS]


def extract_document_text(ext: str, data: bytes) -> str:
    """Safely extract text from validated bytes based on file extension."""
    if ext == ".pdf":
        return _extract_pdf_text(data)
    if ext == ".docx":
        return _extract_docx_text(data)
    if ext in (".txt", ".md"):
        return _extract_plain_text(data)
    raise ValidationError(f"Unsupported extension '{ext}'.")


def save_file_safely(storage_dir: Path, safe_filename: str, data: bytes) -> Path:
    """Save bytes inside storage_dir with a unique UUID prefix, verifying path containment."""
    storage_dir.mkdir(parents=True, exist_ok=True)
    disk_name = f"{uuid.uuid4().hex}_{safe_filename}"
    target = (storage_dir / disk_name).resolve()
    root_resolved = storage_dir.resolve()
    if root_resolved not in target.parents:
        raise ValidationError("Resolved storage path escapes target directory.")
    target.write_bytes(data)
    return target


def delete_file_safely(file_path: str) -> None:
    """Delete a stored file if it exists on disk."""
    try:
        p = Path(file_path)
        if p.exists() and p.is_file():
            os.remove(p)
    except Exception:
        pass
