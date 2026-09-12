"""Hash-bound, read-only document evidence extraction for registered PDF sources.

The document surface deliberately separates deterministic text extraction from
engineering interpretation.  It re-verifies the registered blob on every request,
returns page-addressed text, and creates no source claims or authority by itself.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Mapping

import pypdf
from pypdf import PdfReader

from .stored_source_parser import read_registered_source_bytes


DOCUMENT_EVIDENCE_SCHEMA = "hardware_splicer.document_evidence.v1"
DOCUMENT_EXTRACTION_IMPLEMENTATION = (
    "hardware_splicer.document_evidence.pypdf.v1"
)
MAX_DOCUMENT_PAGES = 512
MAX_PAGE_TEXT_CHARACTERS = 100_000
MAX_PAGE_CHUNK_CHARACTERS = 50_000
MAX_SEARCH_QUERY_CHARACTERS = 256
MAX_SEARCH_RESULTS = 50
MAX_SEARCH_CONTEXT_CHARACTERS = 1_000
MAX_SUPPORTING_TEXT_CHARACTERS = 2_000


@dataclass(frozen=True)
class ExtractedDocument:
    project_id: str
    source_id: str
    content_hash: str
    document_revision: str | None
    pages: tuple[str, ...]
    library_version: str


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_extracted_text(value: str) -> str:
    """Normalize parser output without changing page or character semantics."""

    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")


def normalize_supporting_text(value: str) -> str:
    """Collapse extraction whitespace for stable quoted-support matching."""

    return re.sub(r"\s+", " ", normalize_extracted_text(value)).strip()


@lru_cache(maxsize=8)
def _extract_pdf_pages(content: bytes) -> tuple[tuple[str, ...], str]:
    """Cache deterministic extraction while callers still re-verify blobs per read."""

    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
    except Exception as exc:
        raise ValueError(f"registered PDF cannot be parsed: {exc}") from exc
    if reader.is_encrypted:
        raise ValueError("encrypted PDF sources are not supported")
    if not reader.pages:
        raise ValueError("registered PDF contains no pages")
    if len(reader.pages) > MAX_DOCUMENT_PAGES:
        raise ValueError(
            f"registered PDF exceeds the {MAX_DOCUMENT_PAGES}-page extraction limit"
        )

    pages: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = normalize_extracted_text(page.extract_text() or "")
        except Exception as exc:
            raise ValueError(
                f"registered PDF page {page_number} text extraction failed: {exc}"
            ) from exc
        if len(text) > MAX_PAGE_TEXT_CHARACTERS:
            raise ValueError(
                f"registered PDF page {page_number} exceeds the "
                f"{MAX_PAGE_TEXT_CHARACTERS}-character extraction limit"
            )
        pages.append(text)
    return tuple(pages), str(pypdf.__version__)


def extract_registered_pdf(
    project_id: str,
    source: Mapping[str, Any],
    *,
    project_root: str | None = None,
) -> ExtractedDocument:
    """Re-verify and extract all pages from one registered PDF source."""

    source_id = str(source.get("source_id") or "").strip()
    if not source_id:
        raise ValueError("registered document source requires source_id")
    content_hash = str(source.get("content_hash") or "").strip()
    content = read_registered_source_bytes(
        project_id,
        source,
        project_root=project_root,
    )
    if not content.startswith(b"%PDF-"):
        raise ValueError("registered document source is not a PDF by signature")
    pages, library_version = _extract_pdf_pages(content)

    return ExtractedDocument(
        project_id=project_id,
        source_id=source_id,
        content_hash=content_hash,
        document_revision=(
            str(source.get("revision")) if source.get("revision") is not None else None
        ),
        pages=pages,
        library_version=library_version,
    )


def page_record(document: ExtractedDocument, page_number: int) -> Dict[str, Any]:
    if page_number < 1 or page_number > len(document.pages):
        raise ValueError(
            f"page_number must be between 1 and {len(document.pages)}"
        )
    text = document.pages[page_number - 1]
    return {
        "page_number": page_number,
        "text_characters": len(text),
        "text_sha256": _sha256_text(text),
        "text_available": bool(text.strip()),
    }


def document_index(document: ExtractedDocument) -> Dict[str, Any]:
    return {
        "schema_version": DOCUMENT_EVIDENCE_SCHEMA,
        "project_id": document.project_id,
        "source_id": document.source_id,
        "content_hash": document.content_hash,
        "document_revision": document.document_revision,
        "page_count": len(document.pages),
        "pages": [
            page_record(document, page_number)
            for page_number in range(1, len(document.pages) + 1)
        ],
        "extraction": {
            "implementation": DOCUMENT_EXTRACTION_IMPLEMENTATION,
            "library": "pypdf",
            "library_version": document.library_version,
            "source_hash_reverified": True,
            "text_is_machine_extraction": True,
            "layout_fidelity_proven": False,
        },
        "claims_created": False,
        "authority_unchanged": True,
        "limitations": [
            "Extracted text can omit, reorder, or misread visually encoded PDF content.",
            "Document extraction does not establish claim correctness, physical identity, "
            "or physical authority.",
        ],
    }


def document_page(
    document: ExtractedDocument,
    page_number: int,
    *,
    offset: int = 0,
    max_characters: int = 20_000,
) -> Dict[str, Any]:
    record = page_record(document, page_number)
    text = document.pages[page_number - 1]
    if offset < 0 or offset > len(text):
        raise ValueError(
            f"offset must be between 0 and the page length ({len(text)})"
        )
    if max_characters < 1 or max_characters > MAX_PAGE_CHUNK_CHARACTERS:
        raise ValueError(
            f"max_characters must be between 1 and {MAX_PAGE_CHUNK_CHARACTERS}"
        )
    chunk = text[offset : offset + max_characters]
    next_offset = offset + len(chunk)
    return {
        "schema_version": DOCUMENT_EVIDENCE_SCHEMA,
        "project_id": document.project_id,
        "source_id": document.source_id,
        "content_hash": document.content_hash,
        "document_revision": document.document_revision,
        **record,
        "text": chunk,
        "text_offset": offset,
        "returned_characters": len(chunk),
        "text_truncated": next_offset < len(text),
        "next_offset": next_offset if next_offset < len(text) else None,
        "evidence_locator_candidate": {
            "page": page_number,
            "source_content_hash": document.content_hash,
            "page_text_sha256": record["text_sha256"],
            "extraction_implementation": DOCUMENT_EXTRACTION_IMPLEMENTATION,
        },
        "claims_created": False,
        "authority_unchanged": True,
    }


def search_document(
    document: ExtractedDocument,
    query: str,
    *,
    limit: int = 20,
    context_characters: int = 240,
) -> Dict[str, Any]:
    resolved_query = query.strip()
    if not resolved_query:
        raise ValueError("query must not be blank")
    if len(resolved_query) > MAX_SEARCH_QUERY_CHARACTERS:
        raise ValueError(
            f"query exceeds {MAX_SEARCH_QUERY_CHARACTERS} characters"
        )
    if limit < 1 or limit > MAX_SEARCH_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_SEARCH_RESULTS}")
    if context_characters < 20 or context_characters > MAX_SEARCH_CONTEXT_CHARACTERS:
        raise ValueError(
            "context_characters must be between 20 and "
            f"{MAX_SEARCH_CONTEXT_CHARACTERS}"
        )

    needle = resolved_query.casefold()
    matches: list[Dict[str, Any]] = []
    total_match_count = 0
    for page_number, text in enumerate(document.pages, start=1):
        folded = text.casefold()
        cursor = 0
        page_hash = _sha256_text(text)
        while True:
            position = folded.find(needle, cursor)
            if position < 0:
                break
            total_match_count += 1
            if len(matches) < limit:
                radius = context_characters // 2
                start = max(0, position - radius)
                end = min(len(text), position + len(resolved_query) + radius)
                matches.append(
                    {
                        "page_number": page_number,
                        "match_start": position,
                        "snippet_start": start,
                        "snippet": text[start:end],
                        "page_text_sha256": page_hash,
                    }
                )
            cursor = position + max(1, len(resolved_query))

    return {
        "schema_version": DOCUMENT_EVIDENCE_SCHEMA,
        "project_id": document.project_id,
        "source_id": document.source_id,
        "content_hash": document.content_hash,
        "document_revision": document.document_revision,
        "query": resolved_query,
        "case_sensitive": False,
        "total_match_count": total_match_count,
        "returned_match_count": len(matches),
        "limit": limit,
        "matches": matches,
        "extraction_implementation": DOCUMENT_EXTRACTION_IMPLEMENTATION,
        "claims_created": False,
        "authority_unchanged": True,
    }


def supporting_text_is_present(page_text: str, supporting_text: str) -> bool:
    normalized_support = normalize_supporting_text(supporting_text)
    if not normalized_support:
        return False
    if len(normalized_support) > MAX_SUPPORTING_TEXT_CHARACTERS:
        return False
    return normalized_support in normalize_supporting_text(page_text)


def text_sha256(value: str) -> str:
    """Return the canonical text digest used in persisted extraction locators."""

    return _sha256_text(value)
