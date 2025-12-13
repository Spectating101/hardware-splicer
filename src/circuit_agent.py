
import json
import os
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
import base64
import cv2
import numpy as np
import asyncio

# Import Cerebras client
from openai import AsyncOpenAI

# Import vision components
from vision.enhanced_detector import EnhancedComponentDetector, ComponentDetection

# --- Configuration ---
DEFAULT_KNOWLEDGE_PATH = os.path.join(os.path.dirname(__file__), '../knowledge_base')
CEREBRAS_API_KEY = "csk-34cp53294pcmrexym8h2r4x5cyy2npnrd344928yhf2hpctj"
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
CEREBRAS_MODEL = "llama-3.3-70b"

class CircuitKnowledgeBase:
    """Manages the knowledge base for Circuit-AI."""

    def __init__(self, knowledge_path: str = DEFAULT_KNOWLEDGE_PATH):
        self.knowledge_path = knowledge_path
        self.components = {}
        self.boards = {}
        self.hazards = []
        self.common_ics = []
        self._load_knowledge()
        logger.info(f"CircuitKnowledgeBase initialized from {knowledge_path}")

    def _load_knowledge(self):
        """Loads all JSON files from the knowledge base directory."""
        components_path = os.path.join(self.knowledge_path, 'components')
        boards_path = os.path.join(self.knowledge_path, 'boards')
        safety_path = os.path.join(self.knowledge_path, 'safety')

        # Load generic components
        if os.path.exists(components_path):
            for filename in os.listdir(components_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(components_path, filename)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        # Check if it's the common_ics list or single component
                        if "ics" in data:
                            self.common_ics.extend(data["ics"])
                        else:
                            self.components[data.get('id', filename.replace('.json', ''))] = data

        # Load boards
        if os.path.exists(boards_path):
            for filename in os.listdir(boards_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(boards_path, filename)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        self.boards[data.get('id', filename.replace('.json', ''))] = data
                        
        # Load hazards
        if os.path.exists(safety_path):
            for filename in os.listdir(safety_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(safety_path, filename)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        if "hazards" in data:
                            self.hazards.extend(data["hazards"])

    def get_component_info(self, component_id: str) -> Optional[Dict[str, Any]]:
        return self.components.get(component_id)

    def get_board_info(self, board_id: str) -> Optional[Dict[str, Any]]:
        return self.boards.get(board_id)

class CircuitAgent:
    """
    The core Circuit-AI agent, integrating vision, knowledge, and LLM reasoning.
    """
    def __init__(self, knowledge_path: str = DEFAULT_KNOWLEDGE_PATH):
        self.knowledge = CircuitKnowledgeBase(knowledge_path=knowledge_path)
        self.enhanced_detector = EnhancedComponentDetector(knowledge_base_path=knowledge_path)
        self.cerebras_client = AsyncOpenAI(api_key=CEREBRAS_API_KEY, base_url=CEREBRAS_BASE_URL)
        logger.info("CircuitAgent initialized.")

    async def _send_to_llm(self, messages: List[Dict[str, str]]) -> str:
        try:
            chat_completion = await self.cerebras_client.chat.completions.create(
                model=CEREBRAS_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Error communicating with Cerebras LLM: {e}")
            return "An error occurred while processing with the LLM."

    def _analyze_image_with_vision(self, image_b64: str) -> Tuple[List[ComponentDetection], np.ndarray]:
        try:
            img_bytes = base64.b64decode(image_b64)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            image_np = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image_np is None:
                raise ValueError("Could not decode image from base64.")

            # Enable OCR to help identify boards
            detections = self.enhanced_detector.detect_components(image_np, enable_ocr=True)

            return detections, image_np
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return [], None

    def _enrich_detections_with_knowledge(self, detections: List[ComponentDetection]) -> List[Dict[str, Any]]:
        """
        Enriches detected components with detailed information from the knowledge base.
        Includes:
        1. Direct ID Match
        2. Name Mapping
        3. OCR Board Fallback
        4. Common Mistake Consultant
        5. NEW: Hazard Inspector (Phones/Batteries)
        6. NEW: Common IC Lookup
        """
        enriched = []
        for det in detections:
            item_info = None
            
            # --- 1. Direct ID Match ---
            if det.class_name in self.knowledge.boards:
                item_info = self.knowledge.get_board_info(det.class_name)
            elif det.class_name in self.knowledge.components:
                item_info = self.knowledge.get_component_info(det.class_name)
            
            # --- 2. Name Match / Mapping ---
            if not item_info:
                if det.class_name == "Arduino Uno":
                     item_info = self.knowledge.get_board_info("arduino_uno_r3")
                if not item_info:
                    for b_id, b_data in self.knowledge.boards.items():
                        if b_data.get('name') == det.class_name: 
                            item_info = b_data
                            break
            
            # --- 3. OCR Analysis (Boards, ICs, Hazards) ---
            if det.text_content:
                text = det.text_content.lower()
                
                # A. Board Fallback
                if not item_info:
                    if "raspberry" in text or "pi 4" in text:
                        item_info = self.knowledge.get_board_info("raspberry_pi_4b")
                        if item_info: det.class_name = "Raspberry Pi 4 Model B"
                    elif "esp32" in text:
                        item_info = self.knowledge.get_board_info("esp32_devkit_v1")
                        if item_info: det.class_name = "ESP32 DevKit V1"
                    elif "nano" in text or ("arduino" in text and "v3" in text):
                        item_info = self.knowledge.get_board_info("arduino_nano_v3")
                        if item_info: det.class_name = "Arduino Nano V3"

                # B. Common IC Lookup
                if not item_info:
                    for ic in self.knowledge.common_ics:
                        for keyword in ic["keywords"]:
                            if keyword in text:
                                item_info = {
                                    "name": ic.get("description", "Unknown IC"),
                                    "usage_tip": ic.get("pinout_hint", "")
                                }
                                det.class_name = f"IC: {ic['id'].upper()}"
                                break
                        if item_info: break

                # C. Hazard Inspector (Global Check)
                # Check hazards even if we found info (safety overrides info)
                for hazard in self.knowledge.hazards:
                    for keyword in hazard["keywords"]:
                        if keyword in text:
                            # Append hazard to existing info or create new
                            hazard_msg = f"{hazard['severity']}: {hazard['warning']} {hazard['action']}"
                            if item_info:
                                existing_tip = item_info.get("safety_tip", "")
                                item_info["safety_tip"] = f"{hazard_msg} {existing_tip}"
                            else:
                                item_info = {
                                    "name": "Hazardous Component",
                                    "safety_tip": hazard_msg
                                }
                            # Log critical warnings
                            if hazard['severity'] == 'CRITICAL':
                                logger.warning(f"CRITICAL HAZARD DETECTED: {keyword}")
                            break

            # --- 4. Common Mistake Consultant (Heuristics) ---
            if not item_info:
                lname = det.class_name.lower()
                if "led" in lname:
                    item_info = {
                        "name": "Generic LED",
                        "safety_tip": "CRITICAL: Check polarity! Flat side/short leg is Cathode (GND). Connect Anode (long leg) to VCC via resistor (220-330ohm)."
                    }
                elif "capacitor" in lname:
                    item_info = {
                        "name": "Generic Capacitor",
                        "safety_tip": "If cylindrical (electrolytic), stripe denotes Negative (-). Connecting backward can cause explosion."
                    }
                elif "resistor" in lname:
                    item_info = {
                        "name": "Resistor",
                        "safety_tip": "Non-polarized. Verify value using color bands."
                    }

            if item_info:
                enriched.append({
                    "detection": det,
                    "knowledge_info": item_info
                })
            else:
                enriched.append({
                    "detection": det,
                    "knowledge_info": {"status": "unknown", "description": "No specific knowledge entry found."}
                })
        return enriched

    async def process_request(self, user_query: str, image_b64: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes a user's request, potentially with an image, and returns a response.
        """
        messages = [{"role": "user", "content": user_query}]
        vision_analysis_report = ""
        augmented_image_b64 = None
        raw_image_np = None

        if image_b64:
            logger.info("Image detected, performing vision analysis...")
            detections, raw_image_np = self._analyze_image_with_vision(image_b64)
            enriched_detections = self._enrich_detections_with_knowledge(detections)

            if raw_image_np is not None:
                image_with_overlays = raw_image_np.copy()
                image_with_overlays = self.enhanced_detector.draw_detections(image_with_overlays, detections)

                # PINOUT OVERLAY LOGIC
                for enriched_det in enriched_detections:
                    det = enriched_det["detection"]
                    board_info = enriched_det["knowledge_info"]
                    
                    if board_info.get("headers"):
                        logger.info(f"Drawing pinout overlay for {det.class_name}")
                        image_with_overlays = self.enhanced_detector.draw_pinout_overlay(
                            image_with_overlays, det, board_info
                        )
                
                _, buffer = cv2.imencode('.png', image_with_overlays)
                augmented_image_b64 = base64.b64encode(buffer).decode('utf-8')


            if enriched_detections:
                vision_analysis_report = "Vision Analysis Report:\n"
                for entry in enriched_detections:
                    det = entry["detection"]
                    kb_info = entry["knowledge_info"]
                    vision_analysis_report += (
                        f"- Detected: {det.class_name} (Confidence: {det.confidence:.2f})\n"
                        f"  KB Info: {kb_info.get('name', kb_info.get('status'))}\n"
                    )
                    if kb_info.get("safety_tip"):
                        vision_analysis_report += f"  ⚠️ SAFETY: {kb_info.get('safety_tip')}\n"
                    if kb_info.get("usage_tip"):
                        vision_analysis_report += f"  💡 TIP: {kb_info.get('usage_tip')}\n"
                    
                    if det.text_content:
                        vision_analysis_report += f"  OCR Text: '{det.text_content}'\n"
            else:
                vision_analysis_report = "Vision Analysis Report: No components detected.\n"

            messages.append({"role": "user", "content": f"Image analysis results:\n{vision_analysis_report}"})

        llm_response_content = await self._send_to_llm(messages)

        response = {
            "llm_response": llm_response_content,
            "vision_report": vision_analysis_report,
            "augmented_image_b64": augmented_image_b64
        }
        return response

if __name__ == '__main__':
    # Test stub
    pass
