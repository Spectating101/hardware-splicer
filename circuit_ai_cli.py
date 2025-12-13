#!/usr/bin/env python3
"""
Circuit-AI Interactive CLI

DIY Electronics Assistant for Arduino, Raspberry Pi, and more.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from chatbot_engine import CLIFramework
from circuit_agent import CircuitAgent


def main():
    """Run Circuit-AI interactive CLI"""
    print("\n" + "="*70)
    print("🔧 Circuit-AI - Your DIY Electronics Assistant")
    print("="*70)
    print("\nSpecializing in:")
    print("  - Arduino & Microcontrollers")
    print("  - Raspberry Pi")
    print("  - Component Selection")
    print("  - Wiring & Troubleshooting")
    print("  - Code Generation")
    print("\nType 'help' for available commands, 'quit' to exit")
    print("="*70)

    # Create agent
    agent = CircuitAgent(knowledge_base_path="knowledge_base")

    # Create CLI
    cli = CLIFramework(
        agent=agent,
        app_name="Circuit-AI",
        enable_sessions=True
    )

    # Run interactive mode
    cli.run()


if __name__ == "__main__":
    main()
