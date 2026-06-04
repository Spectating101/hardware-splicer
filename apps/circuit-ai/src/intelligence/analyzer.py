from typing import Dict, List

class CircuitAnalyzer:
    def __init__(self, circuit_data: Dict):
        self.nets = circuit_data.get("nets", {})

    def find_single_node_nets(self) -> List[str]:
        """Find nets that only have 1 connection (floating pins)"""
        floating = []
        for name, data in self.nets.items():
            if len(data["nodes"]) <= 1:
                floating.append(name)
        return floating

    def get_stats(self) -> Dict:
        return {
            "total_nets": len(self.nets),
            "total_pins": sum(len(n["nodes"]) for n in self.nets.values())
        }
