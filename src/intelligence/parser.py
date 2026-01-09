import re
from typing import Dict, List, Any

class KiCadParser:
    """Parses KiCad 6+ S-Expression Netlists (.net)"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nets = {}
        self.components = {}

    def parse(self) -> Dict[str, Any]:
        with open(self.file_path, 'r') as f:
            content = f.read()

        # --- Parse Components ---
        # (components
        #   (comp (ref "R1")
        #     (value "10k")
        #     (footprint "Resistor_SMD:R_0603")
        #   )
        # )
        
        # Capture the components block
        comps_block_match = re.search(r'\(components(.*?)\)\s*\)\s*\(libparts', content, re.DOTALL)
        if not comps_block_match:
             # Try simpler end if libparts is missing
            comps_block_match = re.search(r'\(components(.*?)\)\s*\)\s*\(nets', content, re.DOTALL)
            
        if comps_block_match:
            comps_body = comps_block_match.group(1)
            # Find individual component blocks: (comp (ref "R1") ... )
            # This regex captures the ref and the body of the comp
            comp_matches = re.findall(r'\(comp\s+\(ref\s+"([^"]+)"\)(.*?)\)\s*(?=\(comp|\s*$)', comps_body, re.DOTALL)
            
            for ref, body in comp_matches:
                # Extract value
                val_match = re.search(r'\(value\s+"([^"]+)"\)', body)
                value = val_match.group(1) if val_match else "Unknown"
                
                # Extract footprint
                fp_match = re.search(r'\(footprint\s+"([^"]+)"\)', body)
                footprint = fp_match.group(1) if fp_match else "Unknown"
                
                self.components[ref] = {
                    "value": value,
                    "footprint": footprint
                }
        
        # --- Parse Nets ---
        # Matches: (net (code "1") (name "+3V3") ... )
        net_blocks = re.findall(r'\(net\s+\(code\s+"([^"]+)"\)\s+\(name\s+"([^"]+)"\)(.*?)\)\s*(?=\(net|\)\s*$)', content, re.DOTALL)
        
        for code, name, body in net_blocks:
            nodes = []
            # Find all (node ...) blocks inside the net body
            node_matches = re.findall(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', body)
            for ref, pin in node_matches:
                nodes.append({"ref": ref, "pin": pin})
            
            self.nets[name] = {
                "code": code,
                "nodes": nodes
            }
            
        return {
            "nets": self.nets,
            "components": self.components
        }
