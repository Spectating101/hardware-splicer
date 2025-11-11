#!/usr/bin/env python3
"""
Test Interactive Repair Chatbot

Tests the conversational repair guidance system.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from loguru import logger

from src.intelligence.interactive_repair_chatbot import interactive_repair_chatbot, ConversationState
from src.intelligence.connection_mapper import CircuitSchematic, PinConnection
from src.intelligence.pin_detector import ICDetectionResult, DetectedPin, PinOrientation
from src.intelligence.pinout_database import PackageType


def create_mock_schematic() -> CircuitSchematic:
    """Create a mock Arduino schematic."""
    pins = [
        DetectedPin(pin_number=7, position=(295, 210), confidence=0.7, detection_method="inference"),
    ]

    ic = ICDetectionResult(
        part_number="ATMEGA328P",
        bbox=(300, 200, 500, 400),
        pin_count=28,
        package_type=PackageType.DIP,
        orientation=PinOrientation.UP,
        pins=pins,
        pin1_position=(295, 210),
        confidence=0.7
    )

    return CircuitSchematic(
        ics=[ic],
        connections=[],
        nets=[],
        power_rails={"VCC_5V": 5.0},
        ground_pins=[],
        unconnected_pins=[],
        confidence=0.7
    )


def test_conversation_start():
    """Test starting a conversation."""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Starting Conversation")
    logger.info("="*60)

    schematic = create_mock_schematic()

    # Start conversation
    conv_id = "test_conv_1"
    response = interactive_repair_chatbot.start_conversation(
        conversation_id=conv_id,
        device_type="Arduino Uno",
        schematic=schematic,
        symptoms=["won't upload", "usb not recognized"]
    )

    assert conv_id in interactive_repair_chatbot.conversations, "Conversation not created"
    assert len(response) > 0, "Empty response"
    assert "Arduino" in response or "arduino" in response, "Should mention device"

    conversation = interactive_repair_chatbot.conversations[conv_id]
    assert conversation.state == ConversationState.DIAGNOSING, "Should be in diagnosing state"
    assert len(conversation.messages) == 1, "Should have initial message"

    logger.info(f"✅ Conversation started")
    logger.info(f"Initial response: {response[:100]}...")

    logger.info("✅ Conversation Start: PASSED\n")


def test_diagnostic_flow():
    """Test diagnostic conversation flow."""
    logger.info("="*60)
    logger.info("TEST 2: Diagnostic Flow")
    logger.info("="*60)

    schematic = create_mock_schematic()

    # Start conversation
    conv_id = "test_conv_2"
    response1 = interactive_repair_chatbot.start_conversation(
        conversation_id=conv_id,
        device_type="Arduino Uno",
        schematic=schematic,
        symptoms=["won't upload"]
    )

    logger.info(f"Bot: {response1[:150]}...")

    # User responds about LEDs
    response2 = interactive_repair_chatbot.send_message(conv_id, "Yes, power LED is on")
    logger.info(f"\nBot: {response2[:150]}...")

    # Should ask for voltage measurement
    assert "voltage" in response2.lower() or "measure" in response2.lower(), "Should ask to measure voltage"

    # User provides voltage measurement
    response3 = interactive_repair_chatbot.send_message(
        conv_id,
        "5.1V",
        metadata={"voltage": 5.1}
    )
    logger.info(f"\nBot: {response3[:150]}...")

    conversation = interactive_repair_chatbot.conversations[conv_id]
    assert "voltage" in conversation.measurements, "Should have recorded voltage"
    assert conversation.measurements["voltage"] == 5.1, "Voltage should be 5.1"

    logger.info(f"\n✅ Recorded measurements: {conversation.measurements}")
    logger.info("✅ Diagnostic Flow: PASSED\n")


def test_repair_guidance():
    """Test repair step guidance."""
    logger.info("="*60)
    logger.info("TEST 3: Repair Guidance")
    logger.info("="*60)

    schematic = create_mock_schematic()

    # Start conversation
    conv_id = "test_conv_3"
    response1 = interactive_repair_chatbot.start_conversation(
        conversation_id=conv_id,
        device_type="Arduino Uno",
        schematic=schematic,
        symptoms=["won't upload", "USB chip hot"]
    )

    logger.info(f"Bot: {response1[:100]}...")

    # Trigger USB chip overheat scenario
    response2 = interactive_repair_chatbot.send_message(conv_id, "Yes, LEDs are on")
    logger.info(f"\nBot: {response2[:100]}...")

    # Bot asks for voltage
    response3 = interactive_repair_chatbot.send_message(
        conv_id,
        "5.0V",
        metadata={"voltage": 5.0}
    )
    logger.info(f"\nBot: {response3[:150]}...")

    # Bot should now ask about USB chip or other diagnostics
    # Since symptoms include "USB chip hot", and voltage is OK, bot should ask about it
    response4 = interactive_repair_chatbot.send_message(conv_id, "Yes, the USB chip is very hot")
    logger.info(f"\nBot: {response4[:200]}...")

    conversation = interactive_repair_chatbot.conversations[conv_id]

    # Should have detected USB chip issue
    assert "usb_chip_hot" in conversation.findings, "Should have recorded USB chip hotness"
    assert conversation.findings["usb_chip_hot"] == "yes", "Should be yes"

    # Should have moved to repairing state
    assert conversation.state == ConversationState.REPAIRING, f"Should be repairing, got {conversation.state}"

    # Should warn about disconnecting
    assert "disconnect" in response4.lower() or "unplug" in response4.lower(), "Should warn to disconnect"

    logger.info(f"\n✅ State: {conversation.state}")
    logger.info(f"✅ Findings: {conversation.findings}")
    logger.info("✅ Repair Guidance: PASSED\n")


def test_conversation_history():
    """Test conversation history tracking."""
    logger.info("="*60)
    logger.info("TEST 4: Conversation History")
    logger.info("="*60)

    schematic = create_mock_schematic()

    # Start conversation
    conv_id = "test_conv_4"
    interactive_repair_chatbot.start_conversation(
        conversation_id=conv_id,
        device_type="Arduino Uno",
        schematic=schematic,
        symptoms=["not working"]
    )

    # Exchange messages
    interactive_repair_chatbot.send_message(conv_id, "LEDs are off")
    interactive_repair_chatbot.send_message(conv_id, "4.8V")

    # Get history
    history = interactive_repair_chatbot.get_conversation_history(conv_id)

    assert len(history) == 5, f"Expected 5 messages (1 initial + 2 user + 2 bot), got {len(history)}"
    assert history[0]['role'] == 'assistant', "First message should be from assistant"
    assert history[1]['role'] == 'user', "Second message should be from user"

    logger.info(f"✅ Conversation history:")
    for i, msg in enumerate(history):
        logger.info(f"   {i+1}. [{msg['role']}] {msg['content'][:60]}...")

    logger.info("✅ Conversation History: PASSED\n")


def test_summary_generation():
    """Test diagnostic summary generation."""
    logger.info("="*60)
    logger.info("TEST 5: Summary Generation")
    logger.info("="*60)

    schematic = create_mock_schematic()

    # Start conversation
    conv_id = "test_conv_5"
    interactive_repair_chatbot.start_conversation(
        conversation_id=conv_id,
        device_type="Arduino Uno",
        schematic=schematic,
        symptoms=["bootloader issue"]
    )

    # Add some measurements
    interactive_repair_chatbot.send_message(conv_id, "Yes")
    interactive_repair_chatbot.send_message(conv_id, "5.2V", metadata={"voltage": 5.2})

    # Generate summary
    summary = interactive_repair_chatbot.generate_summary(conv_id)

    assert "Arduino Uno" in summary, "Summary should mention device"
    assert "5.2" in summary, "Summary should include measurement"
    assert "bootloader issue" in summary, "Summary should include symptom"

    logger.info("✅ Generated summary:")
    logger.info(summary)

    logger.info("\n✅ Summary Generation: PASSED\n")


def test_complete_scenario():
    """Test complete repair scenario from start to finish."""
    logger.info("="*60)
    logger.info("TEST 6: Complete Repair Scenario")
    logger.info("="*60)

    schematic = create_mock_schematic()

    # Scenario: USB chip overheating, needs replacement
    conv_id = "test_conv_complete"

    logger.info("--- Starting Conversation ---")
    response = interactive_repair_chatbot.start_conversation(
        conversation_id=conv_id,
        device_type="Arduino Uno",
        schematic=schematic,
        symptoms=["won't upload", "computer doesn't recognize"]
    )
    logger.info(f"Bot: {response}\n")

    logger.info("--- User: LEDs are on ---")
    response = interactive_repair_chatbot.send_message(conv_id, "Yes, power LED is on")
    logger.info(f"Bot: {response}\n")

    logger.info("--- User: Voltage measurement ---")
    response = interactive_repair_chatbot.send_message(conv_id, "5.1V", metadata={"voltage": 5.1})
    logger.info(f"Bot: {response}\n")

    logger.info("--- User: USB chip is hot ---")
    response = interactive_repair_chatbot.send_message(conv_id, "Yes, it's quite hot")
    logger.info(f"Bot: {response}\n")

    conversation = interactive_repair_chatbot.conversations[conv_id]
    assert conversation.state == ConversationState.REPAIRING, "Should be in repair state"

    logger.info("--- User: Ready to repair ---")
    response = interactive_repair_chatbot.send_message(conv_id, "Yes, guide me through replacing it")
    logger.info(f"Bot: {response}\n")

    logger.info("--- Continuing repair steps ---")
    for step_num in range(3):
        response = interactive_repair_chatbot.send_message(conv_id, "Done, what's next?")
        logger.info(f"Bot (Step {step_num + 2}): {response}\n")

    # Final summary
    summary = interactive_repair_chatbot.generate_summary(conv_id)
    logger.info("--- Final Summary ---")
    logger.info(summary)

    logger.info("\n✅ Complete Scenario: PASSED\n")


def main():
    """Run all tests."""
    logger.info("\n" + "="*60)
    logger.info("INTERACTIVE REPAIR CHATBOT TEST")
    logger.info("Testing conversational repair guidance")
    logger.info("="*60)

    try:
        test_conversation_start()
        test_diagnostic_flow()
        test_repair_guidance()
        test_conversation_history()
        test_summary_generation()
        test_complete_scenario()

        logger.info("\n" + "="*60)
        logger.info("✅ ALL CHATBOT TESTS PASSED!")
        logger.info("="*60)
        logger.info("\nInteractive repair chatbot ready!")
        logger.info("The system can now provide conversational, adaptive repair guidance.")
        logger.info("This is THE core vision - making repairs interactive!")

    except AssertionError as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        logger.error(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
