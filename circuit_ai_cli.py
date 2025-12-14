#!/usr/bin/env python3
"""
Circuit-AI Interactive CLI

DIY Electronics Assistant for Arduino, Raspberry Pi, and more.
"""

import sys
import os
import argparse
import base64
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from chatbot_engine import CLIFramework
from circuit_agent import CircuitAgent


def encode_image(image_path):
    """Encode image file to base64 string."""
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)
    
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def main():
    """Run Circuit-AI interactive CLI"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Circuit-AI: Visual Electronics Debugger")
    parser.add_argument("--image", "-i", help="Path to PCB/Component image for visual analysis")
    parser.add_argument("query", nargs="*", help="Question to ask (optional, enters interactive mode if empty)")
    args = parser.parse_args()

    print("\n" + "="*70)
    print("👁️⚡ Circuit-AI - Visual Electronics Debugger")
    print("="*70)

    # Create agent
    agent = CircuitAgent(knowledge_base_path="knowledge_base")

    # Handle One-Shot Mode (Image + Query)
    if args.image:
        query = " ".join(args.query) if args.query else "What do you see in this image?"
        print(f"\n🖼️  Analyzing image: {args.image}")
        print(f"❓ Query: {query}")
        print("-" * 40)
        
        image_b64 = encode_image(args.image)
        
        # Async wrapper for one-shot call
        async def run_one_shot():
            await agent.initialize()
            response = await agent.process_request(query, image_b64=image_b64)
            
            print("\n🤖 Analysis Result:")
            print(response.get("vision_report", "No visual insights."))
            print("\n💬 Answer:")
            print(response.get("llm_response", "No response."))
            
            if response.get("augmented_image_b64"):
                output_path = "analyzed_pcb.png"
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(response["augmented_image_b64"]))
                print(f"\n✅ Augmented image saved to: {output_path}")

        asyncio.run(run_one_shot())
        return

    # Handle Interactive Mode
    print("\nSpecializing in:")
    print("  - Visual PCB Debugging (use --image)")
    print("  - Arduino & Microcontrollers")
    print("  - Component Selection")
    print("\nType 'help' for available commands, 'quit' to exit")
    print("="*70)

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