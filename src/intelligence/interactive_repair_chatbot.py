"""
Interactive Repair Chatbot

THE CORE VISION: Conversational, interactive repair guidance.

Example conversation:
User: "My Arduino won't upload"
Bot: "I see an Arduino Uno. Let me check the board. First, measure voltage at pin 7 (VCC). What do you get?"
User: "5.1V"
Bot: "Good! Power is fine. Now check if the USB chip (U2) is warm to touch. Is it?"
User: "Yes, it's quite hot"
Bot: "That's the problem - CH340 is overheating. This usually means a short. Disconnect USB immediately..."

This makes the repair interactive and adaptive based on what the user finds.
"""

import json
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from src.intelligence.connection_mapper import CircuitSchematic, PinConnection
from src.intelligence.pinout_database import pinout_database
from src.intelligence.repair_guidance import repair_guidance, RepairProcedure
from src.intelligence.safety_validator import safety_validator
from src.intelligence.electrical_analysis import electrical_analyzer
from src.intelligence.common_fault_database import common_fault_database


class ConversationState(Enum):
    """States in the repair conversation."""
    INITIAL = "initial"  # Just started
    DIAGNOSING = "diagnosing"  # Asking questions to identify problem
    MEASURING = "measuring"  # Asked user to measure something
    REPAIRING = "repairing"  # Guiding through repair steps
    VERIFYING = "verifying"  # Checking if repair worked
    COMPLETE = "complete"  # Repair successful
    STUCK = "stuck"  # Can't proceed, need expert help


@dataclass
class ConversationMessage:
    """A message in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)  # measurements, images, etc.


@dataclass
class RepairConversation:
    """A complete repair conversation."""
    conversation_id: str
    device_type: str
    schematic: CircuitSchematic
    symptoms: List[str]
    state: ConversationState
    messages: List[ConversationMessage]
    current_hypothesis: Optional[str] = None
    current_step: int = 0
    measurements: Dict[str, float] = field(default_factory=dict)  # {"vcc_voltage": 5.1, ...}
    findings: Dict[str, str] = field(default_factory=dict)  # {"usb_chip_hot": "yes", ...}


class InteractiveRepairChatbot:
    """Interactive chatbot for conversational repair guidance."""

    def __init__(self):
        """Initialize chatbot."""
        self.conversations: Dict[str, RepairConversation] = {}

        # Diagnostic decision trees
        self.diagnostic_trees = {
            'arduino': self._build_arduino_diagnostic_tree(),
            'router': self._build_router_diagnostic_tree(),
            'esp_module': self._build_esp_diagnostic_tree(),
        }

    def start_conversation(self, conversation_id: str, device_type: str,
                          schematic: CircuitSchematic, symptoms: List[str]) -> str:
        """
        Start a new repair conversation.

        Args:
            conversation_id: Unique conversation ID
            device_type: Type of device (arduino, router, etc.)
            schematic: Circuit schematic from connection_mapper
            symptoms: User-reported symptoms

        Returns:
            Initial bot response
        """
        conversation = RepairConversation(
            conversation_id=conversation_id,
            device_type=device_type,
            schematic=schematic,
            symptoms=symptoms,
            state=ConversationState.INITIAL,
            messages=[]
        )

        self.conversations[conversation_id] = conversation

        # Generate initial response
        response = self._generate_initial_response(conversation)

        # Add to history
        conversation.messages.append(ConversationMessage(
            role="assistant",
            content=response
        ))

        # Move to diagnosing state
        conversation.state = ConversationState.DIAGNOSING

        return response

    def send_message(self, conversation_id: str, user_message: str,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Send user message and get bot response.

        Args:
            conversation_id: Conversation ID
            user_message: User's message
            metadata: Optional metadata (measurements, images)

        Returns:
            Bot response
        """
        if conversation_id not in self.conversations:
            return "ERROR: Conversation not found. Start a new conversation first."

        conversation = self.conversations[conversation_id]

        # Add user message to history
        conversation.messages.append(ConversationMessage(
            role="user",
            content=user_message,
            metadata=metadata or {}
        ))

        # Parse user input for measurements/findings
        self._extract_measurements(conversation, user_message, metadata)

        # Generate response based on current state
        response = self._generate_response(conversation, user_message)

        # Add bot response to history
        conversation.messages.append(ConversationMessage(
            role="assistant",
            content=response
        ))

        return response

    def _generate_initial_response(self, conversation: RepairConversation) -> str:
        """Generate initial greeting and first diagnostic question."""
        device = conversation.device_type
        symptoms = ", ".join(conversation.symptoms)

        # Safety check first
        response = f"I'll help you diagnose and repair your {device}. "
        response += f"You reported: {symptoms}.\n\n"

        # Check common faults database for matching symptoms
        matching_faults = common_fault_database.find_faults_by_symptoms(conversation.symptoms)
        if matching_faults:
            top_fault = matching_faults[0]
            response += f"Based on your symptoms, this could be: **{top_fault.name}**\n"
            response += f"Let's verify with some diagnostic tests.\n\n"

        # Safety warnings
        if "router" in device.lower() or "mains" in symptoms.lower():
            response += "⚠️  SAFETY WARNING: This device may have mains voltage (120V/240V). "
            response += "Unplug from power before opening! ⚠️\n\n"

        if conversation.schematic.ics:
            response += f"I can see {len(conversation.schematic.ics)} ICs on the board:\n"
            for ic in conversation.schematic.ics[:3]:
                response += f"  - {ic.part_number}\n"

        # First diagnostic question
        response += "\nLet's start diagnosing. First question:\n"
        response += "Do you see any LEDs on the board? If yes, are any of them lit?"

        return response

    def _generate_response(self, conversation: RepairConversation, user_input: str) -> str:
        """Generate contextual response based on conversation state."""

        if conversation.state == ConversationState.DIAGNOSING:
            return self._diagnose_step(conversation, user_input)

        elif conversation.state == ConversationState.MEASURING:
            return self._handle_measurement(conversation, user_input)

        elif conversation.state == ConversationState.REPAIRING:
            return self._repair_step(conversation, user_input)

        elif conversation.state == ConversationState.VERIFYING:
            return self._verify_repair(conversation, user_input)

        elif conversation.state == ConversationState.COMPLETE:
            return "Great! The repair is complete. Is there anything else you need help with?"

        elif conversation.state == ConversationState.STUCK:
            return "I've run out of diagnostic steps. This might need an expert. Would you like me to summarize what we've found?"

        return "I'm not sure how to proceed. Can you describe the current state of the device?"

    def _diagnose_step(self, conversation: RepairConversation, user_input: str) -> str:
        """Walk through diagnostic tree."""
        # Simple rule-based diagnostics (in real system, would use LLM here)

        device = conversation.device_type
        user_lower = user_input.lower()

        # Check power
        if "voltage" not in conversation.measurements:
            conversation.state = ConversationState.MEASURING
            return ("I need you to measure voltage. Using a multimeter, measure voltage "
                   "at VCC (power pin). For Arduino, it's pin 7. Black probe to GND, red to VCC. "
                   "What voltage do you read?")

        # Power is OK, check USB
        if any(keyword in " ".join(conversation.symptoms).lower() for keyword in ["usb", "upload", "won't upload", "not recognized"]):
            if "usb_chip_hot" not in conversation.findings:
                return "Is the USB-to-serial chip (small IC near USB port) warm or hot to touch?"

        # Common problems
        if conversation.measurements.get("voltage") and conversation.measurements["voltage"] < 4.5:
            conversation.current_hypothesis = "undervoltage"
            return ("Voltage is too low! Should be 5V ±0.25V. This is likely a power supply problem. "
                   "Check: 1) USB cable, 2) USB port, 3) Voltage regulator on board (might be hot).")

        if conversation.findings.get("usb_chip_hot") == "yes":
            conversation.current_hypothesis = "usb_chip_short"
            conversation.state = ConversationState.REPAIRING
            return ("USB chip is overheating - this usually means a short circuit! "
                   "**DISCONNECT USB IMMEDIATELY**. This can damage your computer. "
                   "The problem is likely a damaged USB chip (CH340/CP2102/FT232). "
                   "Would you like me to guide you through replacing it?")

        # If we have measurements but no clear diagnosis
        conversation.current_step += 1

        if conversation.current_step > 5:
            conversation.state = ConversationState.STUCK
            return "I've checked common issues but can't pinpoint the problem. Let me summarize findings..."

        return "Hmm, let me think... [This is where LLM would generate next diagnostic step]"

    def _handle_measurement(self, conversation: RepairConversation, user_input: str) -> str:
        """Handle measurement response."""
        # Measurement should be in user_input or metadata
        conversation.state = ConversationState.DIAGNOSING  # Go back to diagnosing
        return self._diagnose_step(conversation, user_input)

    def _repair_step(self, conversation: RepairConversation, user_input: str) -> str:
        """Guide through repair steps."""
        hypothesis = conversation.current_hypothesis

        if hypothesis == "usb_chip_short":
            step = conversation.current_step

            steps = [
                "Step 1: Disconnect USB cable and remove board from power.",
                "Step 2: Visually inspect USB chip for burn marks or damaged pins.",
                "Step 3: Check for shorts with multimeter (resistance mode): probe between VCC and GND on USB chip. Should be >10kΩ.",
                "Step 4: If shorted, the USB chip needs replacement. This requires hot air soldering station.",
                "Step 5: Alternative: Use external USB-serial adapter (FTDI/CP2102) connected to RX/TX pins."
            ]

            if step < len(steps):
                conversation.current_step += 1
                response = steps[step]

                if step == len(steps) - 1:
                    conversation.state = ConversationState.VERIFYING
                    response += "\n\nHave you completed the repair? Let's test it."

                return response

        return "Repair procedure not found. Need LLM to generate steps dynamically."

    def _verify_repair(self, conversation: RepairConversation, user_input: str) -> str:
        """Verify if repair worked."""
        user_lower = user_input.lower()

        if any(word in user_lower for word in ["yes", "works", "fixed", "success"]):
            conversation.state = ConversationState.COMPLETE
            return "🎉 Excellent! The repair was successful. Great work!"

        if any(word in user_lower for word in ["no", "doesn't", "still", "not working"]):
            conversation.state = ConversationState.STUCK
            return ("The problem persists. Let's review what we've tried: "
                   "[Summary would go here]. This might need expert diagnosis.")

        return "Did the repair work? Please power on the device and test."

    def _extract_measurements(self, conversation: RepairConversation,
                            user_message: str, metadata: Optional[Dict[str, Any]]):
        """Extract measurements and findings from user input."""
        # Check metadata first
        if metadata:
            if 'voltage' in metadata:
                conversation.measurements['voltage'] = float(metadata['voltage'])
            if 'resistance' in metadata:
                conversation.measurements['resistance'] = float(metadata['resistance'])

        # Parse from text
        user_lower = user_message.lower()

        # Voltage
        import re
        voltage_match = re.search(r'(\d+\.?\d*)\s*v', user_lower)
        if voltage_match:
            conversation.measurements['voltage'] = float(voltage_match.group(1))

        # Yes/No findings
        if any(word in user_lower for word in ["yes", "yeah", "yep", "hot", "warm"]):
            if "hot" in conversation.messages[-2].content.lower():
                conversation.findings['usb_chip_hot'] = "yes"
            elif "led" in conversation.messages[-2].content.lower():
                conversation.findings['led_on'] = "yes"

        if any(word in user_lower for word in ["no", "nope", "cold", "off"]):
            if "hot" in conversation.messages[-2].content.lower():
                conversation.findings['usb_chip_hot'] = "no"
            elif "led" in conversation.messages[-2].content.lower():
                conversation.findings['led_on'] = "no"

    def _build_arduino_diagnostic_tree(self) -> Dict[str, Any]:
        """Build Arduino diagnostic decision tree."""
        return {
            'root': {
                'question': 'Does LED light up?',
                'yes': 'check_usb',
                'no': 'check_power'
            },
            'check_power': {
                'question': 'Measure voltage at pin 7 (VCC)',
                'low': 'power_supply_issue',
                'ok': 'bootloader_issue'
            },
            'check_usb': {
                'question': 'Does computer recognize USB device?',
                'yes': 'bootloader_or_sketch',
                'no': 'usb_chip_issue'
            }
        }

    def _build_router_diagnostic_tree(self) -> Dict[str, Any]:
        """Build router diagnostic tree."""
        return {
            'root': {
                'question': 'Do any LEDs turn on?',
                'yes': 'check_boot_process',
                'no': 'check_power_supply'
            }
        }

    def _build_esp_diagnostic_tree(self) -> Dict[str, Any]:
        """Build ESP module diagnostic tree."""
        return {
            'root': {
                'question': 'Can you enter flash mode (GPIO0 to GND on boot)?',
                'yes': 'flash_successful',
                'no': 'boot_pins_issue'
            }
        }

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Get conversation history for display."""
        if conversation_id not in self.conversations:
            return []

        conversation = self.conversations[conversation_id]
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in conversation.messages
        ]

    def generate_summary(self, conversation_id: str) -> str:
        """Generate summary of what was found during diagnosis."""
        if conversation_id not in self.conversations:
            return "Conversation not found"

        conversation = self.conversations[conversation_id]

        summary = f"## Diagnosis Summary for {conversation.device_type}\n\n"
        summary += f"**Symptoms:** {', '.join(conversation.symptoms)}\n\n"

        if conversation.measurements:
            summary += "**Measurements:**\n"
            for key, value in conversation.measurements.items():
                summary += f"  - {key}: {value}\n"

        if conversation.findings:
            summary += "\n**Findings:**\n"
            for key, value in conversation.findings.items():
                summary += f"  - {key}: {value}\n"

        if conversation.current_hypothesis:
            summary += f"\n**Hypothesis:** {conversation.current_hypothesis}\n"

        summary += f"\n**Current State:** {conversation.state.value}\n"

        return summary


# Global singleton
interactive_repair_chatbot = InteractiveRepairChatbot()
