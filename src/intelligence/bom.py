import csv
import io
from typing import Dict, List

class BomGenerator:
    def __init__(self, circuit_data: Dict):
        self.components = circuit_data.get("components", {})

    def generate_csv(self) -> str:
        """Generate BOM in CSV format"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Reference', 'Value', 'Footprint', 'Quantity'])
        
        # Group by Value/Footprint to find Quantity
        grouped = {}
        for ref, data in self.components.items():
            key = (data['value'], data['footprint'])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(ref)
            
        # Write rows
        for (value, footprint), refs in grouped.items():
            # Sort refs nicely (R1, R2...)
            refs.sort()
            qty = len(refs)
            refs_str = " ".join(refs)
            # Use refs_str in a comment or separate column if needed, 
            # but standard BOM usually lists refs
            
            # Simple BOM format: Ref list, Value, Footprint, Qty
            writer.writerow([refs_str, value, footprint, qty])
            
        return output.getvalue()
