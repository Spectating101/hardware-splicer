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

# Import intelligence components
from intelligence.board_analysis_engine import BoardAnalysisEngine
from intelligence.advanced_trace_follower import AdvancedTraceFollower
from intelligence.salvage_consultant import SalvageConsultant
from intelligence.inspection_diff import InspectionDiff
from intelligence.retro_authenticator import RetroAuthenticator
from intelligence.circuit_graph_solver import CircuitGraphSolver

# --- Configuration ---
DEFAULT_KNOWLEDGE_PATH = os.path.join(os.path.dirname(__file__), '../knowledge_base')
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "csk-34cp53294pcmrexym8h2r4x5cyy2npnrd344928yhf2hpctj")
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
                        try:
                            data = json.load(f)
                            if "ics" in data:
                                self.common_ics.extend(data["ics"])
                            else:
                                self.components[data.get('id', filename.replace('.json', ''))] = data
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to load component file: {filename}")

        # Load boards
        if os.path.exists(boards_path):
            for filename in os.listdir(boards_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(boards_path, filename)
                    with open(filepath, 'r') as f:
                        try:
                            data = json.load(f)
                            self.boards[data.get('id', filename.replace('.json', ''))] = data
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to load board file: {filename}")
                        
        # Load hazards
        if os.path.exists(safety_path):
            for filename in os.listdir(safety_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(safety_path, filename)
                    with open(filepath, 'r') as f:
                        try:
                            data = json.load(f)
                            if "hazards" in data:
                                self.hazards.extend(data["hazards"])
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to load safety file: {filename}")

    def get_component_info(self, component_id: str) -> Optional[Dict[str, Any]]:
        return self.components.get(component_id)

    def get_board_info(self, board_id: str) -> Optional[Dict[str, Any]]:
        return self.boards.get(board_id)

class CircuitAgent:
    """
    The core Circuit-AI agent.
    """
    def __init__(self, knowledge_path: str = DEFAULT_KNOWLEDGE_PATH):
        self.knowledge = CircuitKnowledgeBase(knowledge_path=knowledge_path)
        self.enhanced_detector = EnhancedComponentDetector(knowledge_base_path=knowledge_path)
        
        # Intelligence Modules
        self.analysis_engine = BoardAnalysisEngine()
        self.trace_follower = AdvancedTraceFollower()
        self.salvage_consultant = SalvageConsultant()
        self.inspector = InspectionDiff()
        self.retro_verifier = RetroAuthenticator()
        self.graph_solver = CircuitGraphSolver()
        
        self.cerebras_client = AsyncOpenAI(api_key=CEREBRAS_API_KEY, base_url=CEREBRAS_BASE_URL)
        logger.info("CircuitAgent initialized with Full Intelligence Suite (Pro Mode).")

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

            detections = self.enhanced_detector.detect_components(image_np, enable_ocr=True)

            return detections, image_np
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return [], None

    def _enrich_detections_with_knowledge(self, detections: List[ComponentDetection]) -> List[Dict[str, Any]]:
        """Enriches detected components with detailed information."""
        enriched = []
        for det in detections:
            item_info = None
            if det.class_name in self.knowledge.boards:
                item_info = self.knowledge.get_board_info(det.class_name)
            elif det.class_name in self.knowledge.components:
                item_info = self.knowledge.get_component_info(det.class_name)
            if not item_info:
                if det.class_name == "Arduino Uno":
                     item_info = self.knowledge.get_board_info("arduino_uno_r3")
                if not item_info:
                    for b_id, b_data in self.knowledge.boards.items():
                        if b_data.get('name') == det.class_name: 
                            item_info = b_data
                            break
            if det.text_content:
                text = det.text_content.lower()
                if not item_info:
                    if "raspberry" in text or "pi 4" in text:
                        item_info = self.knowledge.get_board_info("raspberry_pi_4b")
                        if item_info: det.class_name = "Raspberry Pi 4 Model B"
                    elif "esp32" in text:
                        item_info = self.knowledge.get_board_info("esp32_devkit_v1")
                        if item_info: det.class_name = "ESP32 DevKit V1"
                for hazard in self.knowledge.hazards:
                    for keyword in hazard["keywords"]:
                        if keyword in text:
                            hazard_msg = f"{hazard['severity']}: {hazard['warning']} {hazard['action']}"
                            if item_info:
                                existing_tip = item_info.get("safety_tip", "")
                                item_info["safety_tip"] = f"{hazard_msg} {existing_tip}"
                            else:
                                item_info = {"name": "Hazardous Component", "safety_tip": hazard_msg}
                            break
            if item_info:
                enriched.append({"detection": det, "knowledge_info": item_info})
            else:
                enriched.append({"detection": det, "knowledge_info": {"status": "unknown"}})
        return enriched

    def _draw_commercial_overlays(self, image: np.ndarray, detections: List[ComponentDetection], 
                                salvage_report: Dict, retro_report: Dict) -> np.ndarray:
        """Draws specialized business overlays."""
        img_copy = image.copy()
        
        # 1. Draw Jackpots (Gold)
        jackpots = salvage_report.get("jackpots", [])
        for jackpot in jackpots:
            for det in detections:
                if det.text_content and jackpot["found_text"] in det.text_content:
                    x1, y1, x2, y2 = [int(c) for c in det.bbox]
                    cv2.rectangle(img_copy, (x1, y1), (x2, y2), (0, 215, 255), 4)
                    label = f"$$$ {jackpot['type']} $$$"
                    t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                    cv2.rectangle(img_copy, (x1, y1 - t_size[1] - 10), (x1 + t_size[0], y1), (0, 215, 255), -1)
                    cv2.putText(img_copy, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        # 2. Draw Retro Verdict
        if retro_report:
            verdict = retro_report.get("verdict", "")
            h, w = img_copy.shape[:2]
            color = (0, 255, 0) # Green
            if verdict == "FAKE": color = (0, 0, 255) # Red
            elif verdict == "SUSPICIOUS": color = (0, 165, 255) # Orange
            cv2.rectangle(img_copy, (0, 0), (w, 60), color, -1)
            cv2.putText(img_copy, f"VERDICT: {verdict}", (20, 45), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

        return img_copy

    async def process_request(self, user_query: str, image_b64: Optional[str] = None, mode: str = "standard") -> Dict[str, Any]:
        """
        Processes a user's request using Pro-Mode Intelligence.
        """
        messages = [{"role": "user", "content": user_query}]
        vision_analysis_report = ""
        augmented_image_b64 = None
        raw_image_np = None

        if image_b64:
            logger.info(f"Performing analysis in mode: {mode}")
            detections, raw_image_np = self._analyze_image_with_vision(image_b64)
            full_ocr_text = " ".join([d.text_content for d in detections if d.text_content])

            # 1. High-Level Board Analysis
            board_analysis_result = {}
            if raw_image_np is not None:
                board_analysis_result = self.analysis_engine.analyze(raw_image_np, detections)
            
            # 2. Trace & Graph Analysis (Pro Mode)
            trace_analysis_result = {}
            lite_signatures = []
            netlist_text = ""
            
            if raw_image_np is not None:
                try:
                    trace_analysis_result = self.trace_follower.analyze_multilayer_pcb(raw_image_np)
                    
                    # ALPHA-FOLD PRO STEP
                    G = self.graph_solver.build_graph(detections, trace_analysis_result)
                    
                    # A. Lite Solving (Heuristics)
                    lite_res = self.graph_solver.solve_function_lite(G)
                    lite_signatures = lite_res['signatures']
                    
                    # B. Pro Solving (LLM Netlist Analysis)
                    netlist_text = self.graph_solver.generate_text_netlist(G)
                    
                except Exception as e:
                    logger.warning(f"Trace/Graph analysis failed: {e}")

            # 3. Component Enrichment
            enriched_detections = self._enrich_detections_with_knowledge(detections)

            # 4. Feature Modules
            salvage_report = {}
            inspection_report = {}
            retro_report = {}

            if "fake" in user_query.lower() or "real" in user_query.lower() or "verify" in user_query.lower():
                mode = "retro"

            if mode == "salvage" or "salvage" in user_query.lower() or "harvest" in user_query.lower():
                board_type = board_analysis_result.get("board_identification", {}).get("board_type", "unknown")
                salvage_report = self.salvage_consultant.evaluate_harvest_potential(detections, board_type)

            if mode == "inspect" and "Arduino" in board_analysis_result.get("board_identification", {}).get("board_type", ""):
                golden_ref = {"Transformer": 0, "MOSFET": 1, "Capacitor": 2, "Arduino Uno": 1} 
                inspection_report = self.inspector.compare(golden_ref, detections)
            
            if mode == "retro":
                retro_report = self.retro_verifier.verify_cartridge(detections, full_ocr_text)

            # 6. Generate Augmented Image
            if raw_image_np is not None:
                image_with_overlays = self.enhanced_detector.draw_detections(raw_image_np.copy(), detections)
                image_with_overlays = self._draw_commercial_overlays(image_with_overlays, detections, salvage_report, retro_report)
                if mode != "retro":
                    for enriched_det in enriched_detections:
                        det = enriched_det["detection"]
                        board_info = enriched_det["knowledge_info"]
                        if board_info.get("headers"):
                            image_with_overlays = self.enhanced_detector.draw_pinout_overlay(
                                image_with_overlays, det, board_info
                            )
                _, buffer = cv2.imencode('.png', image_with_overlays)
                augmented_image_b64 = base64.b64encode(buffer).decode('utf-8')

            # 7. Construct Report
            vision_analysis_report = "--- VISION SYSTEM REPORT ---\n"
            
            # Add Netlist for LLM reasoning (The Pro Feature)
            if netlist_text:
                 vision_analysis_report += "\n--- DERIVED CIRCUIT TOPOLOGY (PRO) ---\n"
                 vision_analysis_report += "Note: Inferred from visual traces. May contain noise.\n"
                 vision_analysis_report += f"{netlist_text}\n"
            
            if lite_signatures:
                vision_analysis_report += "Topological Structures Detected:\n"
                for sig in lite_signatures:
                    vision_analysis_report += f"- {sig['structure']} (x{sig['count']})\n"

            if retro_report:
                vision_analysis_report += "\n--- RETRO AUTHENTICATOR ---\n"
                vision_analysis_report += retro_report['summary'] + "\n"
            else:
                if board_analysis_result:
                    board_id = board_analysis_result["board_identification"]
                    vision_analysis_report += f"Board Type: {board_id['board_type']} (Confidence: {board_id['confidence']:.0%})\n"
            
            if salvage_report:
                vision_analysis_report += "\n--- SALVAGE CONSULTANT ---\n"
                vision_analysis_report += salvage_report['summary'] + "\n"
            
            if inspection_report:
                vision_analysis_report += "\n--- INSPECTION (BETA) ---\n"
                vision_analysis_report += f"Status: {inspection_report['status']}\n"

            messages.append({"role": "user", "content": f"Here is the visual and topological analysis of the image:\n{vision_analysis_report}\n\nTask: Analyze the circuit functionality based on the components and the Netlist provided. Identify the likely function of the board."})

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
