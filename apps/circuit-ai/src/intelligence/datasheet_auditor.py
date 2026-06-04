"""
Datasheet Auditor Module

Performs 'Automated Design Review' by comparing the physical circuit topology
against standard application circuits known by the LLM (internal datasheet knowledge).

Logic:
1. Identify major ICs (e.g., 'LM386', 'NE555').
2. Extract the physical netlist connected to that IC (from CircuitGraphSolver).
3. Ask LLM: "Does this physical netlist match the recommended datasheet circuit?"
"""

from typing import List, Dict, Any
from loguru import logger
import networkx as nx

class DatasheetAuditor:
    """
    Audits circuit implementation against standard engineering practices.
    """

    # Common ICs that LLMs know well (for prompt optimization)
    SUPPORTED_FAMILIES = [
        "LM", "NE", "TL", "CD", "SN", "ATMEGA", "STM32", "ESP", "ARDUINO"
    ]

    def __init__(self):
        logger.info("DatasheetAuditor initialized")

    def identify_audit_targets(self, detections: List[Any]) -> List[Dict[str, Any]]:
        """
        Selects which components are worth auditing (complex ICs with text).
        """
        targets = []
        for det in detections:
            if det.class_name in ["ic_chip", "MOSFET", "Transistor", "Arduino Uno"] and det.text_content:
                text = det.text_content.upper()
                # Check if text looks like a part number (at least 2 letters, 2 numbers)
                if any(fam in text for fam in self.SUPPORTED_FAMILIES) or len(text) > 4:
                    targets.append({
                        "part_number": text,
                        "class": det.class_name,
                        "bbox": det.bbox,
                        "id": f"{det.class_name}_{text}"
                    })
        return targets

    def generate_audit_prompt(self, target: Dict[str, Any], netlist_text: str) -> str:
        """
        Constructs the engineering prompt for the LLM.
        """
        part = target["part_number"]
        
        prompt = f"""
*** DATASHEET AUDIT TASK ***
Target Component: {part} ({target['class']})

1. RECALL the standard/typical application circuit for the {part} from its datasheet.
2. COMPARE it against the Physical Netlist extracted from the board image below.

PHYSICAL NETLIST (Observed):
{netlist_text}

AUDIT CHECKLIST:
- Are necessary bypass capacitors present (e.g., on VCC pins)?
- Are required external components present (e.g., crystal for MCU, gain resistors for Op-Amp)?
- Are there any obvious missing connections (e.g., floating Ground)?

OUTPUT FORMAT:
- Status: [PASS / WARN / FAIL]
- Missing Components: [List]
- Potential Issues: [Description]
"""
        return prompt

    def audit_component(self, target: Dict[str, Any], G: nx.Graph) -> Dict[str, Any]:
        """
        Extracts the 'Local Netlist' relevant to this specific component
        to save context window and focus the LLM.
        """
        # Find node in graph that matches this target
        target_node = None
        for n, attr in G.nodes(data=True):
            if attr.get('bbox') == target['bbox']:
                target_node = n
                break
        
        local_netlist = ""
        if target_node:
            # Extract 1-hop neighborhood (Nets connected to this IC)
            # And 2-hop components (Components connected to those Nets)
            local_netlist = f"Connections for {target['part_number']}:\n"
            
            neighbors = list(G.neighbors(target_node)) # These are Nets
            for net in neighbors:
                connected_parts = []
                for neighbor_part in G.neighbors(net):
                    if neighbor_part != target_node:
                        # Get component class/type
                        part_type = G.nodes[neighbor_part].get('cls', 'Unknown')
                        edge_conf = G.get_edge_data(net, neighbor_part, {}).get("confidence")
                        if edge_conf is not None:
                            connected_parts.append(f"{part_type} (conf {edge_conf:.2f})")
                        else:
                            connected_parts.append(part_type)
                
                if connected_parts:
                    local_netlist += f"  - Connected via Net '{net}' to: {', '.join(connected_parts)}\n"
        
        if not local_netlist:
            local_netlist = "(No clear trace connections found for this component)"

        return {
            "target": target,
            "local_netlist": local_netlist
        }
