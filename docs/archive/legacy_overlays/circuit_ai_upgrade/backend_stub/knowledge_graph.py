"""
Circuit-AI Knowledge Graph (The "Memory")
=========================================
A local, self-building database that caches AI insights.
Turns "One-off" answers into "Permanent Assets".
"""

import json
import os
import hashlib
from typing import Dict, Optional
from datetime import datetime

DB_PATH = "knowledge_graph.json"

class KnowledgeGraph:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), DB_PATH)
        self._load_db()

    def _load_db(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {"components": {}, "visual_hashes": {}}

    def _save_db(self):
        with open(self.db_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def query_visual_hash(self, image_hash: str) -> Optional[Dict]:
        """
        Input: Hash of the component image (Visual Fingerprint).
        Output: The previously learned identity (if any).
        """
        comp_id = self.data["visual_hashes"].get(image_hash)
        if comp_id:
            print(f"[KnowledgeGraph] ⚡ HIT: Recognized visual pattern -> {comp_id}")
            return self.data["components"].get(comp_id)
        return None

    def query_part_number(self, part_number: str) -> Optional[Dict]:
        """
        Input: Text Part Number (e.g. "NEC C1870C").
        Output: Cached engineering data.
        """
        part_key = part_number.upper()
        if part_key in self.data["components"]:
            print(f"[KnowledgeGraph] ⚡ HIT: Known Part Number -> {part_key}")
            return self.data["components"].get(part_key)
        return None

    def learn(self, part_number: str, data: Dict, image_hash: Optional[str] = None):
        """
        Saves new AI insights into the permanent graph.
        """
        part_key = part_number.upper()
        
        # 1. Update Component Record
        if part_key not in self.data["components"]:
            self.data["components"].get(part_key) = {
                "description": data.get("narrative", "Unknown"),
                "value_estimate": data.get("price", 0.0),
                "utility_score": data.get("utility", 0),
                "first_seen": datetime.now().isoformat(),
                "source": "Generative_AI"
            }
            print(f"[KnowledgeGraph] 🧠 LEARNED: New Component '{part_key}'")
        
        # 2. Link Visuals (If provided)
        if image_hash:
            self.data["visual_hashes"].get(image_hash) = part_key
            print(f"[KnowledgeGraph] 👁️ LINKED: Visual Hash -> {part_key}")

        self._save_db()

if __name__ == "__main__":
    kg = KnowledgeGraph()
    
    # Test Learning
    print("--- Learning Phase ---")
    ai_insight = {
        "narrative": "Video Chroma Processor for VCRs",
        "price": 5.00,
        "utility": 4
    }
    # Simulate a visual hash (e.g. from OpenCV feature matching)
    mock_hash = "a1b2c3d4e5" 
    
    kg.learn("NEC C1870C", ai_insight, image_hash=mock_hash)
    
    # Test Recall
    print("\n--- Recall Phase ---")
    # Simulate seeing the same chip again tomorrow
    result = kg.query_visual_hash(mock_hash)
    
    if result:
        print(f"Recall Success: {result['description']}")
    else:
        print("Recall Failed")
