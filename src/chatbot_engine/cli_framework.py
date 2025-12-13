#!/usr/bin/env python3
"""
CLI Framework - Terminal interface for chatbots

Provides interactive CLI with session management, command parsing,
and user-friendly interface.
"""

import asyncio
import sys
from typing import Optional
from .base_agent import BaseAgent, ChatRequest
from .session_manager import SessionManager, Session
from .streaming_ui import StreamingChatUI


class CLIFramework:
    """
    Terminal-based CLI for chatbot agents

    Example:
        class MyCLI(CLIFramework):
            def __init__(self):
                agent = MyAgent()
                super().__init__(agent, app_name="My Chatbot")

        cli = MyCLI()
        cli.run()
    """

    def __init__(
        self,
        agent: BaseAgent,
        app_name: str = "Chatbot Engine",
        enable_sessions: bool = True,
    ):
        """
        Initialize CLI framework

        Args:
            agent: BaseAgent instance to use
            app_name: Application name for UI
            enable_sessions: Enable session management
        """
        self.agent = agent
        self.app_name = app_name
        self.enable_sessions = enable_sessions
        self.ui = StreamingChatUI(app_name=app_name)
        self.session: Optional[Session] = None
        self.running = False

    async def initialize(self):
        """Initialize agent and setup session"""
        # Initialize agent
        await self.agent.initialize()

        # Create or load session
        if self.enable_sessions:
            # For now, create default session
            # In real app, you'd handle login/session selection
            self.session = SessionManager.create_session(
                user_id="default",
                session_id="cli_session",
            )
            self.agent.set_session(self.session)

    async def process_query(self, query: str) -> str:
        """
        Process user query through agent

        Args:
            query: User's question

        Returns:
            Agent's response text
        """
        request = ChatRequest(
            question=query,
            user_id=self.session.user_id if self.session else "default",
            conversation_id=self.session.id if self.session else "default",
        )

        # Check if agent supports streaming
        if hasattr(self.agent, "process_request_streaming"):
            response_text = await self.ui.stream_agent_response(
                self.agent.process_request_streaming(request)
            )
            return response_text
        else:
            # Non-streaming fallback
            response = await self.agent.process_request(request)
            self.ui.console.print(response.response)
            self.ui.console.print()
            return response.response

    async def interactive_mode(self):
        """
        Run interactive CLI loop

        Handles:
        - User input
        - Query processing
        - Session management
        - Special commands (quit, help, etc)
        """
        await self.initialize()
        self.ui.show_header()

        self.running = True

        try:
            while self.running:
                # Get user input
                try:
                    query = await asyncio.to_thread(
                        input, "\n[You] "
                    )
                except EOFError:
                    break

                query = query.strip()

                # Handle empty input
                if not query:
                    continue

                # Handle special commands
                if query.lower() in ["quit", "exit", "q"]:
                    self.ui.console.print("[dim]Goodbye![/dim]")
                    break

                if query.lower() in ["help", "?"]:
                    self.show_help()
                    continue

                if query.lower() == "clear":
                    self.ui.console.clear()
                    self.ui.show_header()
                    continue

                # Show user message
                self.ui.show_user_message(query)

                # Process query
                try:
                    await self.process_query(query)
                except KeyboardInterrupt:
                    self.ui.console.print("\n[dim]Interrupted[/dim]")
                    continue
                except Exception as e:
                    self.ui.show_error(f"Error: {str(e)}")

        except KeyboardInterrupt:
            self.ui.console.print("\n[dim]Interrupted. Goodbye![/dim]")
        finally:
            await self.cleanup()

    async def single_query(self, query: str):
        """
        Process single query and exit

        Args:
            query: User's question
        """
        await self.initialize()
        await self.process_query(query)
        await self.cleanup()

    def show_help(self):
        """Display help message"""
        self.ui.console.print("\n[bold]Available Commands:[/bold]")
        self.ui.console.print("  quit, exit, q  - Exit the application")
        self.ui.console.print("  help, ?        - Show this help message")
        self.ui.console.print("  clear          - Clear the screen")
        self.ui.console.print()

    async def cleanup(self):
        """Cleanup resources"""
        # Save session if enabled
        if self.session and self.enable_sessions:
            SessionManager.save_session(self.session)

        # Cleanup agent
        await self.agent.cleanup()

    def run(self):
        """
        Run the CLI (entry point)

        This is a convenience method that handles asyncio event loop.
        """
        try:
            asyncio.run(self.interactive_mode())
        except KeyboardInterrupt:
            pass


def create_cli(agent_class, app_name: str = "Chatbot", **agent_kwargs):
    """
    Helper function to quickly create and run a CLI

    Args:
        agent_class: BaseAgent subclass
        app_name: Application name
        **agent_kwargs: Arguments to pass to agent constructor

    Example:
        from chatbot_engine import create_cli
        from my_agent import MyAgent

        create_cli(MyAgent, app_name="My Bot", some_arg="value")
    """
    agent = agent_class(**agent_kwargs)
    cli = CLIFramework(agent, app_name=app_name)
    cli.run()
