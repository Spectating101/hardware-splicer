"""
Chatbot Engine - Reusable AI Agent Framework

A clean, production-ready framework for building chatbots and AI agents.
Extracted from Cite-Agent (10k+ PyPI downloads).
"""

__version__ = "1.0.0"

from .base_agent import BaseAgent, ChatRequest, ChatResponse
from .conversation_archive import ConversationArchive, ArchiveEntry
from .session_manager import SessionManager, Session
from .streaming_ui import StreamingChatUI as StreamingUI
from .cli_framework import CLIFramework

__all__ = [
    "BaseAgent",
    "ChatRequest",
    "ChatResponse",
    "ConversationArchive",
    "ArchiveEntry",
    "SessionManager",
    "Session",
    "StreamingUI",
    "CLIFramework",
]
