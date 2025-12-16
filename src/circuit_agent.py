import json
import os
from typing import Dict, Any, List, Optional, Tuple, Union
from loguru import logger
import base64
import cv2
import numpy as np
import asyncio

# Import Cerebras client
from openai import AsyncOpenAI

# Chatbot framework types (for CLI compatibility)
from chatbot_engine.base_agent import ChatRequest, ChatResponse

# Import vision components
from vision.enhanced_detector import EnhancedComponentDetector, ComponentDetection

# Import intelligence components
from intelligence.board_analysis_engine import BoardAnalysisEngine
from intelligence.advanced_trace_follower import AdvancedTraceFollower
from intelligence.salvage_consultant import SalvageConsultant
from intelligence.inspection_diff import InspectionDiff
from intelligence.retro_authenticator import RetroAuthenticator
from intelligence.datasheet_auditor import DatasheetAuditor
from intelligence.spectral_circuit_analyzer import SpectralCircuitAnalyzer

# --- Configuration ---
DEFAULT_KNOWLEDGE_PATH = os.path.join(os.path.dirname(__file__), '../knowledge_base')
# Env-only; avoid hardcoded key defaults
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
CEREBRAS_MODEL = "llama-3.3-70b"
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() not in ("0", "false", "off")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "10"))
LLM_STUB_RESPONSE = os.getenv("LLM_STUB_RESPONSE", "LLM offline stub response.")

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
        self.initialized = False
        self.session = None
        self.knowledge = CircuitKnowledgeBase(knowledge_path=knowledge_path)
        self.enhanced_detector = EnhancedComponentDetector(knowledge_base_path=knowledge_path)
        
        # Intelligence Modules
        self.analysis_engine = BoardAnalysisEngine()
        self.trace_follower = AdvancedTraceFollower()
        self.salvage_consultant = SalvageConsultant()
        self.inspector = InspectionDiff()
        self.retro_verifier = RetroAuthenticator()
        self.datasheet_auditor = DatasheetAuditor()
        self.spectral_analyzer = SpectralCircuitAnalyzer()
        
        self.cerebras_client = None
        if LLM_ENABLED and CEREBRAS_API_KEY:
            try:
                self.cerebras_client = AsyncOpenAI(api_key=CEREBRAS_API_KEY, base_url=CEREBRAS_BASE_URL)
            except Exception as e:
                logger.warning(f"Could not initialize Cerebras client: {e}")
        elif LLM_ENABLED:
            logger.warning("LLM enabled but CEREBRAS_API_KEY not set; using stub responses.")
        logger.info("CircuitAgent initialized with Full Intelligence Suite (Spectral + Auditor).")

    async def initialize(self, force_reload: bool = False):
        if self.initialized and not force_reload:
            return
        self.initialized = True

    async def cleanup(self):
        return

    def set_session(self, session):
        self.session = session

    async def _send_to_llm(self, messages: List[Dict[str, str]]) -> str:
        if not LLM_ENABLED or not self.cerebras_client:
            return LLM_STUB_RESPONSE
        try:
            chat_completion = await asyncio.wait_for(
                self.cerebras_client.chat.completions.create(
                    model=CEREBRAS_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024,
                ),
                timeout=LLM_TIMEOUT_SECONDS,
            )
            return chat_completion.choices[0].message.content
        except asyncio.TimeoutError:
            logger.error(f"LLM request timed out after {LLM_TIMEOUT_SECONDS}s")
            return LLM_STUB_RESPONSE
        except Exception as e:
            logger.error(f"Error communicating with Cerebras LLM: {e}")
            return LLM_STUB_RESPONSE

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

    async def process_request(self, request: Union[str, ChatRequest], image_b64: Optional[str] = None, mode: str = "standard") -> Union[Dict[str, Any], ChatResponse]:
        """
        Processes a user's request using Pro-Mode Intelligence. Accepts plain string or ChatRequest.
        """
        user_query = request.question if isinstance(request, ChatRequest) else str(request)
        messages = [{"role": "user", "content": user_query}]
        vision_analysis_report = ""
        augmented_image_b64 = None
        raw_image_np = None

        if image_b64:
            logger.info(f"Performing analysis in mode: {mode}")
            detections, raw_image_np = self._analyze_image_with_vision(image_b64)
            full_ocr_text = " ".join([d.text_content for d in detections if d.text_content])

            # Detection quality assessment
            det_count = len(detections)
            avg_conf = float(sum(d.confidence for d in detections) / det_count) if det_count else 0.0
            if det_count == 0:
                detection_quality = "none"
            elif avg_conf >= 0.75:
                detection_quality = "high"
            elif avg_conf >= 0.5:
                detection_quality = "medium"
            else:
                detection_quality = "low"
            detection_summary = {
                "count": det_count,
                "avg_confidence": avg_conf,
                "quality": detection_quality,
                "model_source": getattr(self.enhanced_detector, "model_source", "unknown"),
                "fallback_used": getattr(self.enhanced_detector, "fallback_used", False),
                "custom_model_found": getattr(self.enhanced_detector, "custom_model_found", False),
            }

            # 1. High-Level Board Analysis
            board_analysis_result = {}
            if raw_image_np is not None:
                board_analysis_result = self.analysis_engine.analyze(raw_image_np, detections)
            
            # 2. Trace, Spectral, and Graph Analysis
            trace_analysis_result = {}
            spectral_data = {}
            graph_stats = {}
            graph_inference = []
            graph_result = {}
            graph_connections = []
            netlist_text = ""
            audit_prompts = []
            
            if raw_image_np is not None:
                try:
                    trace_analysis_result = self.trace_follower.analyze_multilayer_pcb(raw_image_np)
                    
                    # Graph analysis (topology + motifs)
                    graph_result = self.graph_solver.analyze(detections, trace_analysis_result)
                    graph_inference = graph_result.get("signatures", [])
                    graph_stats = graph_result.get("stats", {})
                    graph_connections = graph_result.get("connections", [])
                    netlist_text = graph_result.get("netlist_text", "")

                    # Spectral analysis (math view)
                    G_spectral = self.spectral_analyzer.build_graph(detections, trace_analysis_result)
                    spectral_data = self.spectral_analyzer.identify_topology(G_spectral)
                    
                    # DATASHEET AUDIT (kept as stub; can be extended)
                    if mode in ["standard", "inspect", "repair"]:
                        targets = self.datasheet_auditor.identify_audit_targets(detections)
                        for target in targets:
                            audit_data = self.datasheet_auditor.audit_component(target, graph_result.get("graph"))
                            prompt = self.datasheet_auditor.generate_audit_prompt(target, audit_data.get("local_netlist", ""))
                            audit_prompts.append(prompt)
                    
                except Exception as e:
                    logger.warning(f"Trace/Spectral/Graph analysis failed: {e}")

            # 3. Component Enrichment
            enriched_detections = self._enrich_detections_with_knowledge(detections)

            # 4. Feature Modules
            salvage_report = {}
            inspection_report = {}
            retro_report = {}
            allow_downstream = detection_quality in ("high", "medium")

            if "fake" in user_query.lower() or "real" in user_query.lower() or "verify" in user_query.lower():
                mode = "retro"

            if allow_downstream and (mode == "salvage" or "salvage" in user_query.lower() or "harvest" in user_query.lower()):
                board_type = board_analysis_result.get("board_identification", {}).get("board_type", "unknown")
                salvage_report = self.salvage_consultant.evaluate_harvest_potential(detections, board_type)
            elif not allow_downstream:
                salvage_report = {"summary": "Detection quality too low for salvage recommendations."}

            if allow_downstream and mode == "inspect" and "Arduino" in board_analysis_result.get("board_identification", {}).get("board_type", ""):
                golden_ref = {"Transformer": 0, "MOSFET": 1, "Capacitor": 2, "Arduino Uno": 1} 
                inspection_report = self.inspector.compare(golden_ref, detections)
            
            if allow_downstream and mode == "retro":
                retro_report = self.retro_verifier.verify_cartridge(detections, full_ocr_text)
            elif mode == "retro" and not allow_downstream:
                retro_report = {"summary": "Detection quality too low for retro verification.", "verdict": "UNKNOWN"}

            # 6. Generate Augmented Image
            if raw_image_np is not None:
                image_with_overlays = self.enhanced_detector.draw_detections(raw_image_np.copy(), detections)
                image_with_overlays = self._draw_commercial_overlays(image_with_overlays, detections, salvage_report, retro_report)
                if graph_connections:
                    image_with_overlays = self.enhanced_detector.draw_graph_edges(image_with_overlays, graph_connections, detections)
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
            
            if detection_summary:
                vision_analysis_report += f"Detections: {detection_summary.get('count', 0)} (avg conf: {detection_summary.get('avg_confidence', 0):.2f}, quality: {detection_summary.get('quality')}, model: {detection_summary.get('model_source')})\n"
                if detection_summary.get("fallback_used"):
                    vision_analysis_report += "Model fallback in use; accuracy may be reduced.\n"

            # Add Spectral Data (The Math)
            if spectral_data:
                 vision_analysis_report += "\n--- SPECTRAL TOPOLOGY ANALYSIS ---\n"
                 vision_analysis_report += f"Identified Topology: {spectral_data.get('topology_name')}\n"
                 vision_analysis_report += f"Laplacian Spectrum: {spectral_data.get('spectrum')}\n"
                 if spectral_data.get('spectral_error'):
                     vision_analysis_report += f"Spectral Error: {spectral_data.get('spectral_error')}\n"

            if graph_stats:
                vision_analysis_report += f"\nGraph: {graph_stats.get('components', 0)} components, {graph_stats.get('nets', 0)} nets, avg deg {graph_stats.get('avg_component_degree', 0):.2f}\n"
                if graph_stats.get("avg_edge_confidence") is not None:
                    vision_analysis_report += f"Avg edge confidence: {graph_stats.get('avg_edge_confidence', 0):.2f}\n"
            if graph_result and graph_result.get("topology_uncertainty"):
                vision_analysis_report += f"Topology uncertainty: {graph_result.get('topology_uncertainty')} (conf {graph_result.get('topology_confidence', 0):.2f})\n"
            if graph_inference:
                motifs = ", ".join(f"{s['structure']} (x{s['count']})" for s in graph_inference)
                vision_analysis_report += f"Structural motifs: {motifs}\n"
            if graph_result and graph_result.get("library_matches"):
                libs = ", ".join(f"{m['name']} ({m['score']})" for m in graph_result.get("library_matches"))
                vision_analysis_report += f"Library matches: {libs}\n"

            if netlist_text:
                vision_analysis_report += "\n--- CIRCUIT TOPOLOGY ---\n"
                vision_analysis_report += f"{netlist_text}\n"

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

            messages.append({"role": "user", "content": f"Here is the visual analysis:\n{vision_analysis_report}\n\nTask: Provide a comprehensive analysis."})

        llm_response_content = await self._send_to_llm(messages)

        response = {
            "llm_response": llm_response_content,
            "vision_report": vision_analysis_report,
            "augmented_image_b64": augmented_image_b64,
            "detection_summary": detection_summary if image_b64 else {"count": 0, "avg_confidence": 0.0, "quality": "n/a", "model_source": getattr(self.enhanced_detector, "model_source", "unknown"), "fallback_used": getattr(self.enhanced_detector, "fallback_used", False)},
            "graph": {
                "stats": graph_stats,
                "signatures": graph_inference,
                "connections": graph_connections,
                "netlist_text": netlist_text,
                "library_matches": graph_result.get("library_matches", []),
                "topology_confidence": graph_result.get("topology_confidence", 0.0),
            } if image_b64 else {}
        }
        if isinstance(request, ChatRequest):
            return ChatResponse(
                response=response.get("llm_response", ""),
                tools_used=["vision"] if response.get("vision_report") else [],
                model=CEREBRAS_MODEL,
                execution_results={"vision_report": response.get("vision_report"), "graph": response.get("graph"), "detection_summary": response.get("detection_summary")},
                confidence_score=1.0 if response.get("llm_response") else 0.0,
            )
        return response

if __name__ == '__main__':
    # Test stub
    pass
