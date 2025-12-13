#!/usr/bin/env python3
"""
Base Agent - Foundation for AI chatbots and agents

Provides the core infrastructure for building conversational AI systems.
Extend this class and implement process_request() for your custom agent.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class ChatRequest:
    """
    Request object for agent queries

    Attributes:
        question: User's question/query
        user_id: Unique user identifier
        conversation_id: Unique conversation identifier
        context: Additional context data
    """
    question: str
    user_id: str = "default"
    conversation_id: str = "default"
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """
    Response object from agent

    Attributes:
        response: Agent's text response
        tools_used: List of tools/functions called
        reasoning_steps: Step-by-step reasoning process
        model: Model/agent identifier
        timestamp: ISO format timestamp
        tokens_used: Token count (if applicable)
        confidence_score: Confidence in response (0.0-1.0)
        execution_results: Results from tool executions
        api_results: Results from API calls
        error_message: Error message if failed
    """
    response: str
    tools_used: List[str] = field(default_factory=list)
    reasoning_steps: List[str] = field(default_factory=list)
    model: str = "base-agent"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tokens_used: int = 0
    confidence_score: float = 0.0
    execution_results: Dict[str, Any] = field(default_factory=dict)
    api_results: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract base class for AI agents

    Extend this class to create your custom agent. You must implement:
    - initialize(): Setup agent resources
    - process_request(): Handle user queries
    - cleanup(): Clean up resources

    Optional methods:
    - process_request_streaming(): Stream responses
    - register_tools(): Define available tools

    Example:
        class MyAgent(BaseAgent):
            async def initialize(self):
                await super().initialize()
                # Your init code

            async def process_request(self, request: ChatRequest) -> ChatResponse:
                # Your processing logic
                return ChatResponse(response="Your answer")

            async def cleanup(self):
                # Your cleanup code
                await super().cleanup()
    """

    def __init__(self, name: str = "BaseAgent"):
        """
        Initialize base agent

        Args:
            name: Agent name/identifier
        """
        self.name = name
        self.initialized = False
        self.tools: Dict[str, Any] = {}
        self._session = None

    async def initialize(self, force_reload: bool = False):
        """
        Initialize agent resources

        Override this to setup your agent (load models, connect APIs, etc).
        Call super().initialize() to mark as initialized.

        Args:
            force_reload: Force reinitialization even if already initialized
        """
        if self.initialized and not force_reload:
            return

        # Register any tools
        self.register_tools()

        self.initialized = True

    @abstractmethod
    async def process_request(self, request: ChatRequest) -> ChatResponse:
        """
        Process a user request and return response

        This is the main method you must implement for your agent.

        Args:
            request: ChatRequest with user query

        Returns:
            ChatResponse with agent's answer

        Example:
            async def process_request(self, request):
                # Process the query
                answer = self.my_processing_logic(request.question)

                return ChatResponse(
                    response=answer,
                    tools_used=["my_tool"],
                    confidence_score=0.95
                )
        """
        pass

    async def process_request_streaming(self, request: ChatRequest):
        """
        Process request and stream response in chunks

        Override this to support streaming responses.
        Yield strings as they become available.

        Args:
            request: ChatRequest with user query

        Yields:
            str: Response chunks

        Example:
            async def process_request_streaming(self, request):
                words = response.split()
                for word in words:
                    yield word + " "
                    await asyncio.sleep(0.05)
        """
        # Default: fallback to non-streaming
        response = await self.process_request(request)
        yield response.response

    def register_tools(self):
        """
        Register tools/functions available to agent

        Override this to add custom tools.

        Example:
            def register_tools(self):
                self.tools = {
                    "search": self.search_tool,
                    "calculate": self.calculate_tool,
                }
        """
        pass

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Execute a registered tool

        Args:
            tool_name: Name of tool to execute
            **kwargs: Arguments to pass to tool

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found. Available: {list(self.tools.keys())}")

        tool_func = self.tools[tool_name]

        # Handle both sync and async tools
        if asyncio.iscoroutinefunction(tool_func):
            return await tool_func(**kwargs)
        else:
            return tool_func(**kwargs)

    async def cleanup(self):
        """
        Cleanup agent resources

        Override this to cleanup (close connections, save state, etc).
        Call super().cleanup() to mark as uninitialized.
        """
        self.initialized = False

    def set_session(self, session):
        """
        Set the session for this agent

        Args:
            session: Session object with user state
        """
        self._session = session

    def get_session(self):
        """
        Get the current session

        Returns:
            Session object or None
        """
        return self._session

    async def __aenter__(self):
        """Context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.cleanup()

    def __repr__(self):
        status = "initialized" if self.initialized else "uninitialized"
        return f"<{self.__class__.__name__}(name='{self.name}', status='{status}')>"
