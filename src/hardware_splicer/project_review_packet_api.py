"""HTTP surface for the review packet. Read-only: it reports and changes nothing."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Response, status

from .project_api import _project_error
from .project_review_store import ProjectReviewStore
from .project_store import ProjectStore
from .project_thread_store import ProjectThreadStore
from .review_packet import build_review_packet, render_review_packet_markdown


def create_project_review_packet_router(
    store: ProjectStore,
    review_store: ProjectReviewStore | None = None,
    thread_store: ProjectThreadStore | None = None,
) -> APIRouter:
    reviews = review_store or ProjectReviewStore(store)
    threads = thread_store or ProjectThreadStore(store)
    router = APIRouter(prefix="/v1/projects", tags=["projects", "review-packet"])

    @router.get("/{project_id}/review-packet", response_model=None)
    def load_project_review_packet(
        project_id: str,
        revision: int | None = Query(default=None, ge=1),
        format: str = Query(default="json"),
        include_text: bool = Query(default=True),
    ) -> Any:
        if format not in {"json", "markdown"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_request", "message": "format must be json or markdown"},
            )
        try:
            packet = build_review_packet(store, project_id, revision=revision, reviews=reviews, threads=threads, include_free_text=include_text)
        except Exception as exc:
            raise _project_error(exc) from exc
        if format == "markdown":
            name = f"{packet['project']['project_id']}-r{packet['project']['revision']}-review-packet{'' if include_text else '-no-text'}.md"
            return Response(
                content=render_review_packet_markdown(packet).encode("utf-8"),
                media_type="text/markdown; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-cache"},
            )
        body: Dict[str, Any] = {"ok": True, "packet": packet}
        return body

    return router
