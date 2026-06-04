#!/usr/bin/env python3
"""
Session Manager - Handle user sessions and state

Manages user sessions, authentication state, and persistent data.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass
class Session:
    """
    User session with state management

    Attributes:
        id: Unique session identifier
        user_id: Associated user ID
        created_at: Session creation timestamp
        expires_at: Session expiration timestamp
        data: Custom session data
    """
    id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    data: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.now(timezone.utc) > self.expires_at

    def set(self, key: str, value: Any):
        """Set session data"""
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get session data"""
        return self.data.get(key, default)

    def clear(self, key: str):
        """Clear specific session data"""
        self.data.pop(key, None)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "data": self.data,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Session":
        """Create session from dictionary"""
        return Session(
            id=data["id"],
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            data=data.get("data", {}),
        )


class SessionManager:
    """
    Manage user sessions with persistence

    Example:
        # Create session
        session = SessionManager.create_session("user123")

        # Save data
        session.set("context", {"key": "value"})
        SessionManager.save_session(session)

        # Load session
        loaded = SessionManager.load_session(session.id)

        # Check expiration
        if loaded.is_expired():
            SessionManager.refresh_session(loaded.id)
    """

    DEFAULT_SESSION_DIR = Path.home() / ".chatbot_engine" / "sessions"
    DEFAULT_EXPIRY_DAYS = 30

    @classmethod
    def create_session(
        cls,
        user_id: str,
        session_id: Optional[str] = None,
        expiry_days: int = DEFAULT_EXPIRY_DAYS,
    ) -> Session:
        """
        Create a new session

        Args:
            user_id: User identifier
            session_id: Optional custom session ID
            expiry_days: Days until session expires

        Returns:
            New Session object
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=expiry_days)

        session = Session(
            id=session_id or str(uuid.uuid4()),
            user_id=user_id,
            created_at=now,
            expires_at=expires,
        )

        cls.save_session(session)
        return session

    @classmethod
    def save_session(cls, session: Session, session_dir: Optional[Path] = None):
        """
        Save session to disk

        Args:
            session: Session to save
            session_dir: Custom session directory
        """
        dir_path = session_dir or cls.DEFAULT_SESSION_DIR
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path = dir_path / f"{session.id}.json"
        with open(file_path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

    @classmethod
    def load_session(
        cls, session_id: str, session_dir: Optional[Path] = None
    ) -> Optional[Session]:
        """
        Load session from disk

        Args:
            session_id: Session identifier
            session_dir: Custom session directory

        Returns:
            Session object or None if not found
        """
        dir_path = session_dir or cls.DEFAULT_SESSION_DIR
        file_path = dir_path / f"{session_id}.json"

        if not file_path.exists():
            return None

        with open(file_path) as f:
            data = json.load(f)

        return Session.from_dict(data)

    @classmethod
    def delete_session(cls, session_id: str, session_dir: Optional[Path] = None):
        """
        Delete session from disk

        Args:
            session_id: Session identifier
            session_dir: Custom session directory
        """
        dir_path = session_dir or cls.DEFAULT_SESSION_DIR
        file_path = dir_path / f"{session_id}.json"

        if file_path.exists():
            file_path.unlink()

    @classmethod
    def refresh_session(
        cls, session_id: str, expiry_days: int = DEFAULT_EXPIRY_DAYS
    ) -> Optional[Session]:
        """
        Refresh session expiration

        Args:
            session_id: Session identifier
            expiry_days: Days until new expiration

        Returns:
            Updated Session or None if not found
        """
        session = cls.load_session(session_id)
        if not session:
            return None

        session.expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)
        cls.save_session(session)
        return session

    @classmethod
    def list_sessions(
        cls, user_id: Optional[str] = None, session_dir: Optional[Path] = None
    ) -> list[Session]:
        """
        List all sessions, optionally filtered by user

        Args:
            user_id: Filter by user ID
            session_dir: Custom session directory

        Returns:
            List of Session objects
        """
        dir_path = session_dir or cls.DEFAULT_SESSION_DIR

        if not dir_path.exists():
            return []

        sessions = []
        for file_path in dir_path.glob("*.json"):
            with open(file_path) as f:
                data = json.load(f)
            session = Session.from_dict(data)

            if user_id is None or session.user_id == user_id:
                sessions.append(session)

        return sessions

    @classmethod
    def cleanup_expired(cls, session_dir: Optional[Path] = None) -> int:
        """
        Remove all expired sessions

        Args:
            session_dir: Custom session directory

        Returns:
            Number of sessions deleted
        """
        sessions = cls.list_sessions(session_dir=session_dir)
        deleted = 0

        for session in sessions:
            if session.is_expired():
                cls.delete_session(session.id, session_dir=session_dir)
                deleted += 1

        return deleted
