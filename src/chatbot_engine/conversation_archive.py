#!/usr/bin/env python3
"""Lightweight persistent archive for conversation summaries."""

from __future__ import annotations

import json
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class ArchiveEntry:
    """Serialized representation of a conversation turn summary."""

    timestamp: str
    question: str
    summary: str
    tools_used: List[str]
    citations: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "timestamp": self.timestamp,
            "question": self.question,
            "summary": self.summary,
            "tools_used": list(self.tools_used),
        }
        if self.citations:
            data["citations"] = list(self.citations)
        return data

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "ArchiveEntry":
        return ArchiveEntry(
            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
            question=payload.get("question", ""),
            summary=payload.get("summary", ""),
            tools_used=list(payload.get("tools_used", [])),
            citations=list(payload.get("citations", [])) or None,
        )


class ConversationArchive:
    """Stores compact conversation summaries for long-running research threads."""

    def __init__(
        self,
        root: Optional[Path] = None,
        enabled: Optional[bool] = None,
        max_entries: int = 30,
    ) -> None:
        self.enabled = True if enabled is None else bool(enabled)
        self.max_entries = max(1, max_entries)
        env_root = os.getenv("CITE_AGENT_ARCHIVE_DIR")
        final_root = root or Path(env_root) if env_root else root
        self.root = Path(final_root or (Path.home() / ".cite_agent" / "conversation_archive"))
        if self.enabled:
            self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash_identifier(identifier: str) -> str:
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return digest[:16]

    def _conversation_path(self, user_id: str, conversation_id: str) -> Path:
        user_hash = self._hash_identifier(user_id or "anonymous")
        convo_hash = self._hash_identifier(conversation_id or "default")
        return self.root / f"{user_hash}-{convo_hash}.json"

    def record_entry(
        self,
        user_id: str,
        conversation_id: str,
        question: str,
        summary: str,
        tools_used: Optional[List[str]] = None,
        citations: Optional[List[str]] = None,
    ) -> None:
        if not self.enabled:
            return

        entry = ArchiveEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            question=question.strip(),
            summary=summary.strip(),
            tools_used=list(tools_used or []),
            citations=list(citations or []) or None,
        )

        path = self._conversation_path(user_id, conversation_id)
        entries: List[ArchiveEntry] = []
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entries = [ArchiveEntry.from_dict(item) for item in data]
            except Exception:
                entries = []

        entries.append(entry)
        entries = entries[-self.max_entries:]

        serialized = [item.to_dict() for item in entries]
        path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def get_recent_context(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 3,
    ) -> str:
        if not self.enabled:
            return ""

        path = self._conversation_path(user_id, conversation_id)
        if not path.exists():
            return ""

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ""

        if not isinstance(data, list):
            return ""

        entries = [ArchiveEntry.from_dict(item) for item in data][-max(1, limit):]
        if not entries:
            return ""

        lines = ["Archived context from previous sessions:"]
        for item in entries:
            snippet = item.summary.strip().replace("\n", " ")
            if len(snippet) > 220:
                snippet = snippet[:217].rstrip() + "..."
            lines.append(f"• {item.timestamp[:19]} — {snippet}")
        return "\n".join(lines)

    def clear_conversation(self, user_id: str, conversation_id: str) -> None:
        if not self.enabled:
            return
        path = self._conversation_path(user_id, conversation_id)
        if path.exists():
            path.unlink()

    def list_conversations(self) -> List[str]:
        if not self.enabled or not self.root.exists():
            return []
        return [p.name for p in self.root.glob("*.json")]
