from typing import List, Dict, Any
try:
    from .generative_design_agent import GenerativeAgent
except ImportError:
    from generative_design_agent import GenerativeAgent

class KnowledgeBridge:
    def __init__(self):
        self.ai = GenerativeAgent()

    def critique_design_with_context(self, original_plan: Dict, signals: List[Dict]):
        """
        Takes an established design plan and uses recent news signals 
        to provide a 'Safety & Modernity' critique.
        """
        
        prompt = f"""
        Original Engineering Plan: {original_plan}        
        Recent External Signals (Unverified News): 
        {signals}
        
        CRITIQUE TASK:
        1. Review the original plan using standard engineering principles.
        2. Evaluate if any 'External Signals' provide a valid warning or a modern optimization.
        3. If a signal contradicts standard practice, ignore it.
        4. If a signal mentions a known component issue or a significantly better alternative, highlight it as a 'Recommendation'.
        
        Return a 'Critique Report' in the narrative.
        """
        
        return self.ai.generate_solution(prompt, mode="detailed")

if __name__ == "__main__":
    old_plan = {
        "mcu": "STM32F103",
        "regulator": "AMS1117-3.3",
        "notes": "Standard hobbyist power rail."
    }
    
    news_signals = [
        {
            "source": "CNX Software",
            "text": "WCH CH32V003 is now 10% the cost of STM32F103 for simple GPIO tasks."
        },
        {
            "source": "EEVblog Forum",
            "text": "Reports of high failure rates in cheap AMS1117 clones; oscillating under low load."
        }
    ]
    
    bridge = KnowledgeBridge()
    print(">>> RUNNING DESIGN CRITIQUE WITH EXTERNAL SIGNALS <<<")
    result = bridge.critique_design_with_context(old_plan, news_signals)
    
    print("-" * 50)
    print(f"ENGINEER'S VERDICT:\n{result['narrative']}")
    print("-" * 50)
